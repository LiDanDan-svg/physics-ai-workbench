from __future__ import annotations
import json
from typing import Dict, Any
from analytics import student_snapshot

SYSTEM_RULES = """你是一名严谨的高中物理教学诊断助手。你的任务是帮助独立物理老师分析学生学习数据。
必须遵守：
1. 只能基于提供的数据判断，不得编造学生情况、学校情况、家庭情况或考试内容。
2. 区分“事实”“推断”“建议”。样本不足时明确说明不确定性。
3. 不承诺提分，不使用“保证、必然、一定能提高X分”等措辞。
4. 优先识别可行动的问题：知识漏洞、模型识别、受力分析、临界判断、数学处理、综合迁移。
5. 建议必须具体到下一步教学动作、题型或检测方式，避免空泛鼓励。
6. 输出中文 Markdown，结构清晰，适合老师直接使用或二次编辑。
"""


def ai_configured(api_key: str | None) -> bool:
    return bool(api_key and str(api_key).strip())


def _prompt_for(kind: str, student: dict, snapshot: Dict[str, Any]) -> str:
    name = student.get("display_name", "学生")
    profile = {
        "student_id": student.get("student_id"),
        "display_name": name,
        "grade": student.get("grade"),
        "target_score": student.get("target_score"),
        "teacher_notes": student.get("notes", ""),
    }
    data_json = json.dumps({"student": profile, "learning_snapshot": snapshot}, ensure_ascii=False, indent=2)
    if kind == "diagnosis":
        task = "生成教师版学情诊断：一句话结论、证据、趋势、优势、核心瓶颈、错误机制推断（标注推断）、下节课优先处理、验证方法。"
    elif kind == "parent":
        task = "生成家长版阶段学情报告：语言通俗、克制，不制造焦虑；说明进步、当前主要问题、下一阶段教学安排和家长可配合事项。不要承诺提分。"
    elif kind == "weekly":
        task = "生成未来7天/本周教学任务：按课次列目标、典型题训练方向、作业、复测标准；优先处理最薄弱且最可行动的问题。"
    else:
        task = "生成30天提升方案：四周分阶段目标、教学重点、训练结构、周测和进入下一阶段的判断标准。"
    return f"{task}\n\n以下是唯一可用的数据：\n```json\n{data_json}\n```"


def generate_ai_report(kind: str, data: dict, student: dict, api_key: str, model: str = "gpt-5.6-luna", base_url: str = "") -> str:
    from openai import OpenAI
    snapshot = student_snapshot(data, student["student_id"])
    kwargs = {"api_key": api_key}
    if base_url and base_url.strip():
        kwargs["base_url"] = base_url.strip()
    client = OpenAI(**kwargs)
    response = client.responses.create(
        model=model,
        input=SYSTEM_RULES + "\n\n" + _prompt_for(kind, student, snapshot),
    )
    text = getattr(response, "output_text", None)
    if not text:
        raise RuntimeError("AI 返回为空，请检查模型或API配置")
    return text.strip()
