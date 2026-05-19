#!/usr/bin/env python3
"""A local Ollama agent that can execute Python .py scripts as a tool."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib import error, request


SYSTEM_PROMPT = (
    "你是一个可调用工具的本地代码助手。"
    "当用户需要运行 Python 脚本时，调用 run_python_script 工具；"
    "当只需解释或回答时直接回复。"
)


class OllamaClient:
    def __init__(self, base_url: str = "http://127.0.0.1:11434") -> None:
        self.base_url = base_url.rstrip("/")

    def chat(self, model: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "tools": tools,
        }
        data = json.dumps(payload).encode("utf-8")
        req = request.Request(
            f"{self.base_url}/api/chat",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=120) as resp:
                raw = resp.read().decode("utf-8")
        except error.URLError as exc:
            raise RuntimeError(f"Failed to connect to Ollama at {self.base_url}: {exc}") from exc

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Invalid JSON from Ollama: {raw[:500]}") from exc
        return parsed


def run_python_script(path: str, args: list[str] | None = None, timeout: int = 60) -> dict[str, Any]:
    args = args or []
    script = Path(path).expanduser().resolve()
    cwd = Path.cwd().resolve()

    if not script.exists():
        return {"ok": False, "error": f"Script not found: {script}"}
    if script.suffix != ".py":
        return {"ok": False, "error": "Only .py scripts are allowed."}
    if cwd not in script.parents and script != cwd:
        return {
            "ok": False,
            "error": f"Script must stay inside working directory: {cwd}",
        }

    cmd = [sys.executable, str(script), *args]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"Execution timed out after {timeout}s", "cmd": cmd}

    return {
        "ok": proc.returncode == 0,
        "cmd": cmd,
        "returncode": proc.returncode,
        "stdout": proc.stdout[-6000:],
        "stderr": proc.stderr[-6000:],
    }


def tool_schema() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "run_python_script",
                "description": "Execute a local Python .py script in current working directory.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Relative or absolute script path."},
                        "args": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "CLI arguments for the script.",
                        },
                        "timeout": {"type": "integer", "description": "Timeout in seconds."},
                    },
                    "required": ["path"],
                },
            },
        }
    ]


def run_agent(model: str, task: str, base_url: str) -> str:
    client = OllamaClient(base_url=base_url)
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": task},
    ]

    for _ in range(8):
        response = client.chat(model=model, messages=messages, tools=tool_schema())
        message = response.get("message", {})
        messages.append(message)

        tool_calls = message.get("tool_calls") or []
        if not tool_calls:
            return message.get("content", "")

        for call in tool_calls:
            fn = call.get("function", {})
            name = fn.get("name")
            arguments = fn.get("arguments") or {}
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    arguments = {"path": arguments}

            if name == "run_python_script":
                result = run_python_script(
                    path=arguments.get("path", ""),
                    args=arguments.get("args", []),
                    timeout=int(arguments.get("timeout", 60)),
                )
            else:
                result = {"ok": False, "error": f"Unknown tool: {name}"}

            messages.append(
                {
                    "role": "tool",
                    "name": name,
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )

    return "Reached max tool-call iterations without final answer."


def main() -> None:
    parser = argparse.ArgumentParser(description="Local Ollama Python-script agent")
    parser.add_argument("task", help="Task to give the agent")
    parser.add_argument("--model", default="qwen2.5:latest", help="Ollama model name")
    parser.add_argument("--base-url", default=os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434"))
    args = parser.parse_args()

    answer = run_agent(model=args.model, task=args.task, base_url=args.base_url)
    print(answer)


if __name__ == "__main__":
    main()
