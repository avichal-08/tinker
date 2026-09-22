import inspect
import json
import os
from typing import Any, Callable

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel

from src.safety.executor import (
    execute_cache_cleanup,
    execute_docker_cleanup,
    execute_terminate_process,
)
from src.tools.scanner import (
    scan_developer_caches,
    scan_docker_bloat,
    scan_project_artifacts,
    scan_windows_bloat,
)
from src.tools.sensors import (
    get_disk_usage,
    get_listening_ports,
    get_power_and_thermal_stats,
    get_system_stats,
    get_top_processes,
)

load_dotenv()

client = OpenAI(
    api_key=os.environ.get("GROQ_API_KEY"), base_url="https://api.groq.com/openai/v1"
)

SYSTEM_PROMPT = """You are Computer Mechanic, an evidence-driven AI agent that diagnoses and fixes computer issues.
You must follow this loop: Observe → Investigate → Diagnose → Plan → Act → Verify.

When asked to clean up space or memory:
1. Run scanners to find targets.
2. IMMEDIATELY call clean_cache(target_id) or terminate_process(pid) for the targets you want to fix. DO NOT ask the user for permission in text. The tool itself will automatically pause and securely prompt the user.
3. If the tool returns that permission was denied, stop and report it.
4. If approved and successful, verify the recovered resources based on the tool's return data.

Format your final output strictly as:
Observed: [Hard data]
Action Taken: [What was cleaned/killed and how much space/memory was verified as freed, or what was denied]
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
    {
        "type": "function",
        "function": {
            "name": "terminate_process",
            "description": "Terminate a process by its PID to free up memory. MUST obtain user approval first.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pid": {
                        "type": "integer",
                        "description": "The PID of the process to kill",
                    },
                    "name": {
                        "type": "string",
                        "description": "The name of the process (for the UI prompt)",
                    },
                    "expected_recovery_mb": {
                        "type": "number",
                        "description": "Expected RAM recovery in MB",
                    },
                },
                "required": ["pid", "name", "expected_recovery_mb"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scan_docker_bloat",
            "description": "Scan the Docker daemon for dangling images, stopped containers, and unused volumes. Returns targets with IDs and sizes.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scan_windows_bloat",
            "description": "Scan for Windows system bloat (like Windows Update cache or Crash Dumps).",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scan_project_artifacts",
            "description": "Scan the current working directory for heavy project artifacts like node_modules, .venv, or target folders.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_listening_ports",
            "description": "Get a list of all open network ports and the processes (PIDs) listening on them.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_power_and_thermal_stats",
            "description": "Get battery status, power limits, and CPU frequency to check for thermal throttling or battery drain.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]

AVAILABLE_FUNCTIONS: dict[str, Callable[..., Any]] = {
    "get_system_stats": get_system_stats,
    "get_top_processes": get_top_processes,
    "get_disk_usage": get_disk_usage,
    "scan_developer_caches": scan_developer_caches,
    "scan_docker_bloat": scan_docker_bloat,
    "scan_windows_bloat": scan_windows_bloat,
    "scan_project_artifacts": scan_project_artifacts,
    "get_listening_ports": get_listening_ports,
    "get_power_and_thermal_stats": get_power_and_thermal_stats,
}


def run_diagnostic(
    user_query: str,
    on_tool_call: Callable[[str], None] | None = None,
    on_approval: Callable[[str, float, str], bool] | None = None,
    chat_history: list[dict] | None = None,
) -> tuple[str, list[Any]]:

    messages: list[Any] = []

    if chat_history is None:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    else:
        messages = chat_history.copy()

    messages.append({"role": "user", "content": user_query})

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
            return (message.content or "No diagnosis could be determined.", messages)

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

                all_targets = (
                    scan_developer_caches()
                    + scan_docker_bloat()
                    + scan_windows_bloat()
                    + scan_project_artifacts()
                )

                target = next((t for t in all_targets if t.id == target_id), None)

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
                    if target.category == "docker":
                        result = execute_docker_cleanup(target.id)
                    else:
                        result = execute_cache_cleanup(target.path, target.id)

            elif function_name == "terminate_process":
                pid = int(arguments.get("pid", 0))
                proc_name = str(arguments.get("name", f"PID {pid}"))
                expected_mb = float(arguments.get("expected_recovery_mb", 0.0))

                if on_approval and not on_approval(
                    f"Process: {proc_name} (PID: {pid})", expected_mb, "MEDIUM"
                ):
                    result = {
                        "success": False,
                        "message": "Action aborted: User denied permission.",
                    }
                else:
                    result = execute_terminate_process(pid)

            else:
                function_to_call = AVAILABLE_FUNCTIONS.get(function_name)
                if not function_to_call:
                    continue
                sig = inspect.signature(function_to_call)
                safe_args = {k: v for k, v in arguments.items() if k in sig.parameters}

                result = function_to_call(**safe_args)

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
