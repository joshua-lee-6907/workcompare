#!/usr/bin/env python3
"""Conversational Ollama agent: dialogue -> generate/update JSON -> run fixed script -> continue dialogue."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib import error, request

SYSTEM_PROMPT = (
    "你是一个任务编排助手。"
    "你需要根据用户对话生成或更新 JSON 配置，然后运行固定 Python 脚本。"
    "如果信息不足，先提出澄清问题；如果信息充分，只输出 JSON 对象。"
)


class OllamaClient:
    def __init__(self, base_url: str = "http://127.0.0.1:11434") -> None:
        self.base_url = base_url.rstrip("/")

    def chat(self, model: str, messages: list[dict[str, Any]]) -> dict[str, Any]:
        payload = {"model": model, "messages": messages, "stream": False}
        req = request.Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=120) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except error.URLError as exc:
            raise RuntimeError(f"Failed to connect Ollama: {exc}") from exc


def safe_resolve(path: str, cwd: Path) -> Path:
    p = Path(path).expanduser().resolve()
    if cwd != p and cwd not in p.parents:
        raise ValueError(f"Path must stay inside working directory: {cwd}")
    return p


def launch_visualizer(script: Path, input_json: Path) -> tuple[subprocess.Popen[str] | None, dict[str, Any]]:
    cmd = [sys.executable, str(script), str(input_json)]
    try:
        proc = subprocess.Popen(cmd, cwd=str(Path.cwd()), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except Exception as exc:
        return None, {"ok": False, "error": f"failed to launch: {exc}", "cmd": cmd}

    time.sleep(0.6)
    if proc.poll() is not None:
        out, err = proc.communicate()
        return None, {"ok": False, "error": "visualizer exited immediately", "returncode": proc.returncode, "stdout": out[-6000:], "stderr": err[-6000:], "cmd": cmd}
    return proc, {"ok": True, "pid": proc.pid, "cmd": cmd}


def stop_process(proc: subprocess.Popen[str] | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()


def try_parse_json(text: str) -> dict[str, Any] | None:
    text = text.strip()
    if not text:
        return None
    candidates = [text]
    if "```" in text:
        parts = text.split("```")
        candidates.extend(part.strip() for part in parts if part.strip())
    for c in candidates:
        if c.startswith("json"):
            c = c[4:].strip()
        try:
            data = json.loads(c)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            continue
    return None


def interactive_loop(model: str, base_url: str, script: Path, input_json_path: Path, schema_text: str, timeout: int) -> None:
    client = OllamaClient(base_url)
    history: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    print("输入 quit 退出。")
    visualizer_proc: subprocess.Popen[str] | None = None
    while True:
        user = input("\n你: ").strip()
        if user.lower() in {"quit", "exit", "q"}:
            break
        history.append({"role": "user", "content": user})

        prompt = (
            "当前目标脚本会读取一个 JSON 配置并启动 Excel 可视化。\n"
            f"JSON 参考说明:\n{schema_text}\n"
            "若信息不足请提问；若信息足够请仅输出 JSON 对象。"
        )
        work_messages = history + [{"role": "system", "content": prompt}]
        reply = client.chat(model=model, messages=work_messages).get("message", {}).get("content", "")
        history.append({"role": "assistant", "content": reply})

        payload = try_parse_json(reply)
        if payload is None:
            print(f"助手: {reply}")
            continue

        input_json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        stop_process(visualizer_proc)
        visualizer_proc, result = launch_visualizer(script, input_json_path)
        summary = json.dumps(result, ensure_ascii=False, indent=2)
        print("\n=== GENERATED_JSON ===")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        print("\n=== SCRIPT_RESULT ===")
        print(summary)
        if result.get("ok"):
            print("助手: 绘图程序已启动。你可以继续输入新需求，我会重写 JSON 并刷新绘图。")
        history.append({"role": "user", "content": f"绘图脚本执行状态如下，请继续协助我优化配置或排错:\n{summary}"})

    stop_process(visualizer_proc)


def main() -> None:
    parser = argparse.ArgumentParser(description="Conversational JSON->Python orchestrator")
    parser.add_argument("--script", default="excel_visualizer.py", help="固定执行脚本")
    parser.add_argument("--input-json", default="agent_input.json", help="生成 JSON 文件")
    parser.add_argument("--schema", default="excel_visualizer_skill.json", help="JSON 说明/skill 文件")
    parser.add_argument("--model", default="qwen2.5:latest")
    parser.add_argument("--base-url", default=os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434"))
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()

    cwd = Path.cwd().resolve()
    script = safe_resolve(args.script, cwd)
    input_json_path = safe_resolve(args.input_json, cwd)
    schema_path = safe_resolve(args.schema, cwd)
    if not script.exists() or script.suffix != ".py":
        raise RuntimeError(f"Invalid script path: {script}")
    schema_text = schema_path.read_text(encoding="utf-8") if schema_path.exists() else "{}"
    interactive_loop(args.model, args.base_url, script, input_json_path, schema_text, args.timeout)


if __name__ == "__main__":
    main()
