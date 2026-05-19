#!/usr/bin/env python3
"""Local Ollama agent: understand request -> generate JSON input -> run one fixed Python script."""

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
    "你是一个 JSON 输入生成助手。"
    "你的任务是根据用户需求，为目标 Python 脚本生成输入 JSON。"
    "你必须只输出一个 JSON 对象，不要输出 markdown、解释、代码块。"
)


class OllamaClient:
    def __init__(self, base_url: str = "http://127.0.0.1:11434") -> None:
        self.base_url = base_url.rstrip("/")

    def chat(self, model: str, messages: list[dict[str, Any]]) -> dict[str, Any]:
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
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
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Invalid JSON from Ollama: {raw[:500]}") from exc


def safe_resolve(path: str, cwd: Path) -> Path:
    resolved = Path(path).expanduser().resolve()
    if cwd != resolved and cwd not in resolved.parents:
        raise ValueError(f"Path must stay inside working directory: {cwd}")
    return resolved


def read_schema(schema_path: Path | None) -> str:
    if not schema_path:
        return "未提供 schema，按最合理的结构生成 JSON。"
    text = schema_path.read_text(encoding="utf-8")
    return f"请严格参考以下 JSON schema/示例（纯文本）:\n{text}"


def generate_input_json(model: str, base_url: str, task: str, schema_text: str) -> dict[str, Any]:
    client = OllamaClient(base_url=base_url)
    user_prompt = (
        f"用户需求：{task}\n"
        f"{schema_text}\n"
        "现在只输出 JSON 对象。"
    )
    response = client.chat(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )
    content = response.get("message", {}).get("content", "").strip()
    if not content:
        raise RuntimeError("Model returned empty content.")

    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Model output is not valid JSON: {content[:500]}") from exc


def run_script_with_json(script: Path, input_json: Path, timeout: int) -> dict[str, Any]:
    cmd = [sys.executable, str(script), str(input_json)]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(Path.cwd()),
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate JSON with Ollama and run one fixed Python script")
    parser.add_argument("task", help="Natural language requirement from user")
    parser.add_argument("--script", required=True, help="Target Python script path. It will receive one arg: input.json")
    parser.add_argument("--input-json", default="agent_input.json", help="JSON file path to write")
    parser.add_argument("--schema", help="Optional schema/example file for expected JSON structure")
    parser.add_argument("--model", default="qwen2.5:latest", help="Ollama model name")
    parser.add_argument("--base-url", default=os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434"))
    parser.add_argument("--timeout", type=int, default=60, help="Script execution timeout in seconds")
    args = parser.parse_args()

    cwd = Path.cwd().resolve()
    script = safe_resolve(args.script, cwd)
    input_json_path = safe_resolve(args.input_json, cwd)
    schema_path = safe_resolve(args.schema, cwd) if args.schema else None

    if not script.exists() or script.suffix != ".py":
        raise RuntimeError(f"Invalid script path: {script}")

    schema_text = read_schema(schema_path)
    payload = generate_input_json(args.model, args.base_url, args.task, schema_text)
    input_json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    result = run_script_with_json(script, input_json_path, args.timeout)

    print("=== GENERATED_JSON ===")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print("=== SCRIPT_RESULT ===")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
