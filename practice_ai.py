from __future__ import annotations

import json
import re
import uuid
from typing import Any, Dict, List

from analytics import student_snapshot, student_questions

DEFAULT_PRACTICE_MODEL = "qwen3.8-flash"

PRACTICE_SYSTEM = """你是一名严谨的高中物理教师与原创练习设计助手。
任务：根据学生学情生成原创、可讲解、可复测的针对性练习。
规则：
1. 只基于给定学情决定训练方向，不编造学生个人情况。
2. 题目必须原创，不要复制、改写成高度近似的已上传原题，不要复述长篇试卷文本。
3. 每题都要给标准答案、关键步骤、知识点、能力维度、难度1-5、易错点、验收点。
4. 数值题应尽量给出可核算的数值条件；答案必须自洽。若存在多解，要说明条件。
5. 对AI生成的题目必须提醒教师审核后再发给学生。
6. 输出严格JSON，不要Markdown代码块。
"""


def _extract_json(text: str) -> Any:
    text = (text or "").strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    cleaned = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except Exception:
        pass
    a, b = cleaned.find("{"), cleaned.rfind("}")
    if a >= 0 and b > a:
        return json.loads(cleaned[a:b+1])
    raise ValueError("AI返回内容不是可解析的JSON")


def _context(data: dict, student: dict, selected_topics: List[str] | None = None) -> Dict[str, Any]:
    snap = student_snapshot(data, student["student_id"])
    qdf = student_questions(data, student["student_id"])
    recent = []
    if not qdf.empty:
        for _, row in qdf.tail(12).iterrows():
            recent.append({
                "topic": str(row.get("topic", "")),
                "difficulty": int(row.get("difficulty", 3) or 3),
                "score": float(row.get("score", 0) or 0),
                "max_score": float(row.get("max_score", 0) or 0),
                "error_type": str(row.get("error_type", "")),
                "stem_summary": str(row.get("stem_summary", ""))[:120],
            })
    return {
        "student": {
            "student_id": student.get("student_id"),
            "grade": student.get("grade"),
            "target_score": student.get("target_score"),
        },
        "selected_topics": selected_topics or [],
        "learning_snapshot": snap,
        "recent_question_metadata": recent,
    }


def generate_practice_set(
    data: dict,
    student: dict,
    api_key: str,
    base_url: str,
    model: str = DEFAULT_PRACTICE_MODEL,
    question_count: int = 5,
    selected_topics: List[str] | None = None,
    difficulty_mode: str = "由易到难",
    style: str = "高考常见模型",
) -> Dict[str, Any]:
    from openai import OpenAI

    if not api_key:
        raise RuntimeError("未配置 DASHSCOPE_API_KEY")
    question_count = max(2, min(12, int(question_count)))
    ctx = _context(data, student, selected_topics)
    prompt = PRACTICE_SYSTEM + f"""
请生成 {question_count} 道练习。
难度结构：{difficulty_mode}
题目风格：{style}
如果 selected_topics 非空，优先围绕这些知识点；否则按学习快照中的优先薄弱项安排。
题型可以混合选择、实验、计算，但必须适合该年级。

学情数据：
{json.dumps(ctx, ensure_ascii=False, indent=2)}

返回JSON：
{{
  "title":"",
  "training_goal":"",
  "teacher_note":"AI生成题需教师审核后使用",
  "questions":[
    {{
      "no":1,
      "topic":"",
      "skill":"",
      "difficulty":3,
      "question_type":"计算",
      "question":"完整原创题目",
      "answer":"答案",
      "solution":"关键步骤",
      "common_trap":"",
      "acceptance":"掌握标准"
    }}
  ]
}}
"""
    client = OpenAI(api_key=api_key.strip(), base_url=base_url.strip())
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": PRACTICE_SYSTEM},
            {"role": "user", "content": prompt},
        ],
        temperature=0.45,
    )
    obj = _extract_json(completion.choices[0].message.content or "")
    if not isinstance(obj, dict):
        raise ValueError("练习生成结果格式错误")
    qs = obj.get("questions") or []
    if not isinstance(qs, list):
        qs = []
    clean = []
    for i, q in enumerate(qs[:question_count], start=1):
        if not isinstance(q, dict):
            continue
        try:
            diff = int(q.get("difficulty", 3))
        except Exception:
            diff = 3
        clean.append({
            "no": i,
            "topic": str(q.get("topic", "未分类")),
            "skill": str(q.get("skill", "模型识别")),
            "difficulty": max(1, min(5, diff)),
            "question_type": str(q.get("question_type", "计算")),
            "question": str(q.get("question", "")).strip(),
            "answer": str(q.get("answer", "")).strip(),
            "solution": str(q.get("solution", "")).strip(),
            "common_trap": str(q.get("common_trap", "")).strip(),
            "acceptance": str(q.get("acceptance", "")).strip(),
        })
    return {
        "practice_id": "P" + uuid.uuid4().hex[:10].upper(),
        "student_id": student.get("student_id"),
        "title": str(obj.get("title") or "个性化物理训练"),
        "training_goal": str(obj.get("training_goal") or ""),
        "teacher_note": str(obj.get("teacher_note") or "AI生成题需教师审核后使用"),
        "model": model,
        "questions": clean,
    }


def practice_markdown(p: Dict[str, Any], include_answers: bool = True) -> str:
    lines = [f"# {p.get('title','个性化物理训练')}", "", f"训练目标：{p.get('training_goal','')}", "", "> AI生成内容，请教师审核后使用。", ""]
    for q in p.get("questions", []):
        lines += [
            f"## 第{q.get('no')}题｜{q.get('topic')}｜难度{q.get('difficulty')}",
            "",
            q.get("question", ""),
            "",
        ]
        if include_answers:
            lines += [
                f"**答案：** {q.get('answer','')}",
                "",
                f"**解析：** {q.get('solution','')}",
                "",
                f"**易错点：** {q.get('common_trap','')}",
                "",
                f"**验收标准：** {q.get('acceptance','')}",
                "",
            ]
    return "\n".join(lines)
