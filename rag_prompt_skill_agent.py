import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Any, Tuple, Iterable

import requests


PROMPT_FILE = "agent_prompt.txt"
SKILL_FILE = "agent_skills.json"
MEMORY_FILE = "memory_db.json"
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL = "qwen2.5:latest"
SAVE_TRIGGER = "正确并保存"


DEFAULT_PROMPT = """你是一个受限知识对话 Agent。
你只能基于以下三类内容回答：
1) prompt 规则本身
2) skill 知识库
3) 历史记忆库

严格要求：
- 不允许编造任何超出以上三类来源的信息。
- 如果找不到足够依据，必须明确说“当前知识库没有直接答案”。
- 你需要提出 1~3 个澄清问题，帮助用户逐步接近正确答案。
- 当用户输入“正确并保存”时，将上一轮用户问题与助理回答保存到记忆库。
"""

DEFAULT_SKILLS = {
    "skills": [
        {
            "name": "受限问答",
            "description": "只允许从 prompt/skill/记忆库检索回答，不可外推。",
            "examples": [
                "先查 skill，再查 memory，相似条目优先。",
                "查不到时要承认未知并提澄清问题。"
            ]
        },
        {
            "name": "逐步逼近",
            "description": "当信息不足时，通过提问补足条件。",
            "examples": [
                "你想问的是产品功能、配置，还是排障步骤？",
                "请给出关键名词或完整场景。"
            ]
        }
    ]
}


@dataclass
class Turn:
    question: str
    answer: str
    created_at: str


def ensure_files():
    if not os.path.exists(PROMPT_FILE):
        with open(PROMPT_FILE, "w", encoding="utf-8") as f:
            f.write(DEFAULT_PROMPT)

    if not os.path.exists(SKILL_FILE):
        with open(SKILL_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_SKILLS, f, ensure_ascii=False, indent=2)

    if not os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump({"turns": []}, f, ensure_ascii=False, indent=2)


def load_prompt() -> str:
    with open(PROMPT_FILE, "r", encoding="utf-8") as f:
        return f.read().strip()


def load_skills() -> Dict[str, Any]:
    with open(SKILL_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def load_memory() -> Dict[str, Any]:
    with open(MEMORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_memory(memory: Dict[str, Any]):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(memory, f, ensure_ascii=False, indent=2)


def _zh_ngrams(text: str, n_values: Iterable[int] = (2, 3)) -> List[str]:
    grams = []
    chars = re.sub(r"[^\u4e00-\u9fff]", "", text)
    for n in n_values:
        if len(chars) >= n:
            grams.extend([chars[i:i+n] for i in range(len(chars) - n + 1)])
    return grams


def tokenize(text: str) -> List[str]:
    text = text.lower()
    zh_chunks = re.findall(r"[\u4e00-\u9fff]+", text)
    en_chunks = re.findall(r"[a-z0-9_\-]+", text)

    tokens = []
    tokens.extend(en_chunks)
    tokens.extend(zh_chunks)
    for chunk in zh_chunks:
        tokens.extend(_zh_ngrams(chunk))
    return [t for t in tokens if t]


def score_similarity(query: str, target: str) -> float:
    q = set(tokenize(query))
    t = set(tokenize(target))
    if not q or not t:
        return 0.0

    jaccard = len(q & t) / len(q | t)
    query_l = query.lower()
    target_l = target.lower()
    substring_bonus = 0.0
    if query_l and target_l:
        if query_l in target_l or target_l in query_l:
            substring_bonus = 0.25

    return min(1.0, jaccard + substring_bonus)




def parse_memory_turns(memory: Dict[str, Any]) -> List[Turn]:
    turns: List[Turn] = []

    # 格式1：{"turns": [{"question":..., "answer":...}]}
    for t in memory.get("turns", []):
        q = str(t.get("question", "")).strip()
        a = str(t.get("answer", "")).strip()
        if q and a:
            turns.append(Turn(q, a, str(t.get("created_at", ""))))

    # 格式2：{"messages": [{"role":"user|assistant", "content":...}, ...]}
    msgs = memory.get("messages", [])
    if isinstance(msgs, list):
        pending_q = ""
        for m in msgs:
            role = str(m.get("role", "")).strip().lower()
            content = str(m.get("content", "")).strip()
            if not content:
                continue
            if role == "user":
                pending_q = content
            elif role == "assistant" and pending_q:
                turns.append(Turn(pending_q, content, str(m.get("created_at", ""))))
                pending_q = ""

    return turns

def retrieve_context(user_input: str, skills: Dict[str, Any], memory: Dict[str, Any], top_k: int = 5) -> Tuple[List[str], List[Turn]]:
    skill_texts = []
    for s in skills.get("skills", []):
        blob = f"{s.get('name', '')} {s.get('description', '')} {' '.join(s.get('examples', []))}"
        sim = score_similarity(user_input, blob)
        if sim > 0:
            skill_texts.append((sim, blob))

    mem_turns: List[Turn] = []
    for turn in parse_memory_turns(memory):
        blob = f"{turn.question} {turn.answer}"
        sim = score_similarity(user_input, blob)
        if sim > 0:
            mem_turns.append((sim, turn))

    skill_texts.sort(key=lambda x: x[0], reverse=True)
    mem_turns.sort(key=lambda x: x[0], reverse=True)

    top_skill = [t for _, t in skill_texts[:top_k]]
    top_memory = [t for _, t in mem_turns[:top_k]]
    return top_skill, top_memory


def build_llm_prompt(base_prompt: str, user_input: str, skill_ctx: List[str], mem_ctx: List[Turn]) -> str:
    skills_text = "\n".join([f"- {x}" for x in skill_ctx]) if skill_ctx else "- (无匹配 skill)"
    memory_text = "\n".join(
        [f"- Q: {t.question}\n  A: {t.answer}\n  Time: {t.created_at}" for t in mem_ctx]
    ) if mem_ctx else "- (无匹配记忆)"

    return f"""{base_prompt}

【可用 Skill 匹配】
{skills_text}

【可用历史记忆匹配】
{memory_text}

【当前用户问题】
{user_input}

请严格遵守：
1) 仅使用以上内容回答。
2) 若信息不足，输出：当前知识库没有直接答案。
3) 并附加“下一步建议：”后给出最多3个澄清问题。
"""


def call_ollama(prompt: str) -> str:
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.2
        }
    }
    r = requests.post(OLLAMA_URL, json=payload, timeout=120)
    r.raise_for_status()
    data = r.json()
    return data.get("response", "").strip()


def save_last_turn(memory: Dict[str, Any], question: str, answer: str):
    memory.setdefault("turns", []).append({
        "question": question,
        "answer": answer,
        "created_at": datetime.utcnow().isoformat() + "Z"
    })
    save_memory(memory)


def main():
    ensure_files()
    prompt = load_prompt()
    skills = load_skills()
    memory = load_memory()

    last_q = None
    last_a = None

    print("受限 RAG Agent 已启动（基于本地 Ollama: qwen2.5:latest）")
    print("输入 exit 退出；输入 '正确并保存' 保存上一轮问答到记忆库。")

    while True:
        user_input = input("\n你: ").strip()
        if not user_input:
            continue

        if user_input.lower() in {"exit", "quit"}:
            print("再见。")
            break

        if user_input == SAVE_TRIGGER:
            if last_q and last_a:
                memory = load_memory()
                save_last_turn(memory, last_q, last_a)
                print("助手: 已保存到记忆库。")
            else:
                print("助手: 暂无可保存的上一轮问答。")
            continue

        skill_ctx, mem_ctx = retrieve_context(user_input, skills, memory)
        llm_prompt = build_llm_prompt(prompt, user_input, skill_ctx, mem_ctx)

        try:
            answer = call_ollama(llm_prompt)
        except Exception as e:
            answer = f"调用 Ollama 失败：{e}"

        print(f"助手: {answer}")
        last_q = user_input
        last_a = answer


if __name__ == "__main__":
    main()
