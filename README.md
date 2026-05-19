# workcompare

## 对话式 Ollama -> JSON -> Excel 可视化 Agent

现在支持你要求的联动流程：

1. 用户与大模型持续对话。
2. 大模型理解需求后，生成/更新 JSON 配置文件。
3. Agent 将 JSON 输入 `excel_visualizer.py`（固定脚本）并执行。
4. 执行结果回注入对话，继续调试，直到完成。

## 新增文件

- `ollama_python_agent.py`：对话式编排 Agent
- `excel_visualizer.py`：你提供的可视化程序改造成“从 JSON 读取配置”
- `excel_visualizer_skill.json`：给大模型的 JSON 结构 skill 文件

## 使用方式

```bash
ollama serve
python ollama_python_agent.py \
  --model qwen2.5:latest \
  --script ./excel_visualizer.py \
  --schema ./excel_visualizer_skill.json
```

进入交互后直接输入需求，例如：

- “读取 `./data/test.xlsx` 的 `Sheet1`，X 轴用时间，Y 轴用温度和湿度，折线+散点图。”

当模型信息不足时，会先追问；信息足够时输出 JSON 并自动执行脚本。

## JSON 示例

```json
{
  "file_path": "./data/demo.xlsx",
  "sheet_name": "Sheet1",
  "x_var": "时间",
  "y_vars": ["温度", "湿度"],
  "plot_mode": "line_scatter"
}
```
