# workcompare

## 本地受限 RAG 对话 Agent（Ollama + qwen2.5:latest）

新增脚本：`rag_prompt_skill_agent.py`

### 功能
- 仅从以下三类内容检索并回答：
  - `agent_prompt.txt`
  - `agent_skills.json`
  - `memory_db.json`
- 若无匹配信息，会提示：`当前知识库没有直接答案`，并提出澄清问题逐步逼近答案。
- 当用户输入：`正确并保存`，会把上一轮「用户问题 + 助理回答」保存到记忆库。
- 兼容两种历史记忆格式：
  - `{"turns": [{"question","answer"}]}`
  - `{"messages": [{"role","content"}]}`（自动将 user/assistant 配对为可检索问答）
- 检索增强：中文 2/3-gram + 子串匹配加权，降低“近似问法检索不到”的问题。

### 运行
1. 本地启动 Ollama，并确保已拉取模型：`qwen2.5:latest`
2. 安装依赖：
   ```bash
   pip install requests
   ```
3. 运行：
   ```bash
   python rag_prompt_skill_agent.py
   ```

### 文件说明
- `rag_prompt_skill_agent.py`：主程序
- `agent_prompt.txt`：系统约束 prompt
- `agent_skills.json`：skill 配置
- `memory_db.json`：历史记忆库
