# workcompare

## Ollama JSON-to-Python Agent（轻量版）

`ollama_python_agent.py` 改为**固定执行一个指定 Python 脚本**，不再让模型做多轮工具调用，降低对模型性能的要求。

工作流：
1. 大模型理解用户需求。
2. 大模型只生成一个 JSON 对象。
3. Agent 将 JSON 写入文件（默认 `agent_input.json`）。
4. Agent 执行你指定的 `.py` 脚本，并把 JSON 文件路径作为唯一参数传入。

---

## 1) 准备模型

```bash
ollama pull qwen2.5:latest
ollama show qwen2.5:latest
```

确认 digest 包含你指定的版本（例如 `845dbda0ea48`）。

## 2) 启动 Ollama

```bash
ollama serve
```

## 3) 运行 Agent

```bash
python ollama_python_agent.py "帮我生成一个用于统计分析的输入" \
  --script ./main.py
```

可选参数：

```bash
python ollama_python_agent.py "生成电商订单分析输入" \
  --script ./main.py \
  --input-json ./tmp/input.json \
  --schema ./input_schema.txt \
  --model qwen2.5:latest \
  --base-url http://127.0.0.1:11434 \
  --timeout 120
```

## 4) 你的 Python 脚本约定

你的目标脚本需要接收一个参数（JSON 文件路径），例如：

```python
# demo_script.py
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = json.load(f)

print("received:", data)
```

## 5) 安全限制

- `--script` / `--input-json` / `--schema` 必须在当前工作目录内。
- `--script` 必须是存在的 `.py` 文件。
