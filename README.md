# workcompare

## Ollama Python Script Agent

新增 `ollama_python_agent.py`：基于本地 Ollama 模型（默认 `qwen2.5:latest`）的工具调用 Agent，可按需执行 `.py` 脚本。

### 1) 准备模型

```bash
ollama pull qwen2.5:latest
ollama show qwen2.5:latest
```

确认模型 digest 包含你指定的版本（例如 `845dbda0ea48`）。

### 2) 启动 Ollama

```bash
ollama serve
```

### 3) 运行 Agent

```bash
python ollama_python_agent.py "请运行 ./main.py 并总结输出"
```

可选参数：

```bash
python ollama_python_agent.py "运行脚本" --model qwen2.5:latest --base-url http://127.0.0.1:11434
```

### 4) 行为说明

- Agent 通过 Ollama `/api/chat` + tools/function calling 与模型交互。
- 当模型决定调用 `run_python_script` 时，Agent 会执行指定 `.py` 文件并将 stdout/stderr 回传给模型。
- 默认限制：脚本需位于当前工作目录内，避免越界执行。
