import json
import os
from typing import Any, Callable

from openai import OpenAI
from pydantic import BaseModel

from safety import execute_cache_cleanup
from scanner import scan_developer_caches
from tools import get_disk_usage, get_system_stats, get_top_processes

client = OpenAI(
    api_key=os.environ.get("GROQ_API_KEY"), base_url="https://api.groq.com/openai/v1"
)

SYSTEM_PROMPT = """You are Computer Mechanic, an evidence-driven AI agent that diagnoses and fixes computer issues.
You must follow this loop: Observe → Investigate → Diagnose → Plan → Act → Verify.

When asked to clean up space or if disk space is low:
1. Run scan_developer_caches() to find safe targets.
2. IMMEDIATELY call clean_cache(target_id) for the targets you want to clean. DO NOT ask the user for permission in text. The tool itself will automatically pause and securely prompt the user.
3. If the tool returns that permission was denied, stop and report it.
4. If approved and successful, verify the recovered space based on the tool's return data.

Format your final output strictly as:
Observed: [Hard data]
Action Taken: [What was cleaned and how much space was verified as freed, or what was denied]
Current Status: [New system state]
"""

TOOLS: list[Any] = [
    {
        "type": "function",
        "function": {
            "name": "get_system_stats",
            "description": "Get high-level CPU, RAM, and Disk usage.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_top_processes",
            "description": "Get top memory-consuming processes.",
            "parameters": {
                "type": "object",
                "properties": {"limit": {"type": "integer"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_disk_usage",
            "description": "Get detailed disk usage statistics.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scan_developer_caches",
            "description": "Scan for safe-to-clean developer caches and temp files. Returns targets with IDs and sizes.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "clean_cache",
            "description": "Clean a specific cache by its ID (e.g., 'npm_cache'). MUST obtain user approval first.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_id": {
                        "type": "string",
                        "description": "The ID of the cache to clean",
                    }
                },
                "required": ["target_id"],
            },
        },
    },
]

AVAILABLE_FUNCTIONS: dict[str, Callable[..., Any]] = {
    "get_system_stats": get_system_stats,
    "get_top_processes": get_top_processes,
    "get_disk_usage": get_disk_usage,
    "scan_developer_caches": scan_developer_caches,
}


def run_diagnostic(
    user_query: str,
    on_tool_call: Callable[[str], None] | None = None,
    on_approval: Callable[[str, float, str], bool] | None = None,
) -> str:
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
            extra_body={"disable_tool_validation": True},
        )

        message = response.choices[0].message
        messages.append(message)

        if not message.tool_calls:
            return message.content or "No diagnosis could be determined."

        for tool_call in message.tool_calls:
            tool_func = getattr(tool_call, "function", None)
            if not tool_func:
                continue

            raw_name = tool_func.name
            function_name = raw_name.split("<")[0]
            arguments = json.loads(tool_func.arguments) if tool_func.arguments else {}

            if on_tool_call:
                on_tool_call(function_name)

            if function_name == "clean_cache":
                target_id = arguments.get("target_id")
                targets = scan_developer_caches()
                target = next((t for t in targets if t.id == target_id), None)

                if not target:
                    result = {
                        "success": False,
                        "message": f"Cache ID '{target_id}' not found.",
                    }
                elif on_approval and not on_approval(
                    target.name, target.size_mb, target.risk_level
                ):
                    result = {
                        "success": False,
                        "message": "Action aborted: User denied permission.",
                    }
                else:
                    result = execute_cache_cleanup(target.path, target.id)
            else:
                function_to_call = AVAILABLE_FUNCTIONS.get(function_name)
                if not function_to_call:
                    continue
                result = function_to_call(**arguments)

            if isinstance(result, BaseModel):
                content_str = result.model_dump_json()
            elif isinstance(result, list):
                content_str = json.dumps(
                    [
                        item.model_dump() if isinstance(item, BaseModel) else item
                        for item in result
                    ]
                )
            else:
                content_str = json.dumps(result)

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": raw_name,
                    "content": content_str,
                }
            )
