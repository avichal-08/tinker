import json
import os
from typing import Any, Callable

from openai import OpenAI

from tools import get_disk_usage, get_system_stats, get_top_processes

client = OpenAI(
    api_key=os.environ.get("GROQ_API_KEY"), base_url="https://api.groq.com/openai/v1"
)

SYSTEM_PROMPT = """You are Computer Mechanic, an evidence-driven AI agent that diagnoses computer issues.
You must follow this loop: Observe → Investigate → Diagnose.
NEVER guess the problem. Always use your tools to inspect the system first.

When you provide your final diagnosis, format it strictly as:
Observed: [Hard data from tools]
Hypothesis: [Your reasoning]
Recommended action: [What the user should do]
"""

TOOLS: list[Any] = [
    {
        "type": "function",
        "function": {
            "name": "get_system_stats",
            "description": "Get high-level CPU, RAM, and Disk usage percentages to identify system pressure.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_top_processes",
            "description": "Get the top processes consuming the most memory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Number of processes to return (default is 5)",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_disk_usage",
            "description": "Get detailed disk usage statistics for the primary partition.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]

AVAILABLE_FUNCTIONS: dict[str, Callable[..., Any]] = {
    "get_system_stats": get_system_stats,
    "get_top_processes": get_top_processes,
    "get_disk_usage": get_disk_usage,
}

def run_diagnostic(
    user_query: str, on_tool_call: Callable[[str], None] | None = None
) -> str:
    """Runs the diagnostic loop and returns the final markdown diagnosis."""
    messages: list[Any] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_query},
    ]

    while True:
        response = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
        )

        message = response.choices[0].message
        messages.append(message)

        if not message.tool_calls:
            return message.content or "No diagnosis could be determined."

        for tool_call in message.tool_calls:
            tool_func = getattr(tool_call, "function", None)
            if not tool_func:
                continue

            function_name = tool_func.name
            arguments = json.loads(tool_func.arguments) if tool_func.arguments else {}

            if on_tool_call:
                on_tool_call(function_name)

            function_to_call = AVAILABLE_FUNCTIONS.get(function_name)
            if not function_to_call:
                continue

            result = function_to_call(**arguments)

            if hasattr(result, "model_dump_json"):
                content_str = result.model_dump_json()
            elif isinstance(result, list):
                content_str = json.dumps(
                    [
                        item.model_dump() if hasattr(item, "model_dump") else item
                        for item in result
                    ]
                )
            else:
                content_str = json.dumps(result)

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": function_name,
                    "content": content_str,
                }
            )


if __name__ == "__main__":
    run_diagnostic("Why is my computer slow?")
