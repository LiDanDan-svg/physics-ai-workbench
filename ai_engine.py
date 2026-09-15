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
6. 对“可改善失分量”只能作为样本内估算，必须提醒并非提分承诺。
7. 输出中文 Markdown，结构清晰，适合老师直接使用或二次编辑。
"""

DEFAULT_DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_QWEN_MODEL = "qwen3.8-flash"


def ai_configured(api_key: str | None) -> bool:
    return bool(api_key and str(api_key).strip())


def build_ai_payload(student: dict, snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """只发送教学所需的最小化数据。默认不发送学生姓名、学校等直接识别信息。"""
    profile = {
        "student_id": student.get("student_id"),
        "grade": student.get("grade"),
        "target_score": student.get("target_score"),
        "teacher_notes": student.get("notes", ""),
    }
    return {"student": profile, "learning_snapshot": snapshot}


def ai_payload_preview(data: dict, student: dict) -> Dict[str, Any]:
    return build_ai_payload(student, student_snapshot(data, student["student_id"]))


def _prompt_for(kind: str, payload: Dict[str, Any]) -> str:
    data_json = json.dumps(payload, ensure_ascii=False, indent=2)
    if kind == "diagnosis":
        task = (
            "生成教师版学情诊断。按以下结构输出："
            "一句话结论；事实证据；学习趋势；优势；核心瓶颈；"
            "错误机制推断（必须明确标注为推断）；下节课优先处理；"
            "建议训练题型；复测方法；数据局限。"
        )
    elif kind == "parent":
        task = (
            "生成家长版阶段学情报告。语言通俗、克制，不制造焦虑；"
            "说明阶段变化、当前主要问题、下一阶段教学安排和家长可配合事项。"
            "不要使用过多技术术语，不承诺提分。"
        )
    elif kind == "weekly":
        task = (
            "生成未来7天/本周教学任务。按课次列出：目标、典型题训练方向、"
            "课堂动作、课后作业、复测标准；优先处理最薄弱且最可行动的问题。"
        )
    else:
        task = (
            "生成30天提升方案。分4周输出：阶段目标、教学重点、训练结构、"
            "作业与周测、进入下一阶段的判断标准；最后给出风险点和调整条件。"
        )
    return f"{task}\n\n以下是唯一可用的数据：\n```json\n{data_json}\n```"


def _extract_chat_text(response) -> str:
    try:
        return response.choices[0].message.content or ""
    except Exception:
        return ""


def generate_ai_report(
    kind: str,
    data: dict,
    student: dict,
    api_key: str,
    model: str = DEFAULT_QWEN_MODEL,
    base_url: str = DEFAULT_DASHSCOPE_BASE_URL,
) -> str:
    """
    阿里云百炼 / 通义千问中国大陆版。
    使用 OpenAI Python SDK 调用百炼 OpenAI 兼容接口。
    优先使用 Responses API；若当前模型/账户的 Responses 能力异常，
    自动回退到 Chat Completions。
    """
    from openai import OpenAI

    if not ai_configured(api_key):
        raise RuntimeError("尚未配置 DASHSCOPE_API_KEY")

    base_url = (base_url or DEFAULT_DASHSCOPE_BASE_URL).strip()
    model = (model or DEFAULT_QWEN_MODEL).strip()
    payload = build_ai_payload(student, student_snapshot(data, student["student_id"]))
    prompt = SYSTEM_RULES + "\n\n" + _prompt_for(kind, payload)

    client = OpenAI(api_key=api_key.strip(), base_url=base_url)

    # 百炼当前支持 OpenAI 兼容 Responses API；为兼容权限/模型差异，失败时回退 Chat。
    response_error = None
    try:
        response = client.responses.create(model=model, input=prompt)
        text = getattr(response, "output_text", None)
        if text and str(text).strip():
            return str(text).strip()
    except Exception as e:
        response_error = e

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_RULES},
                {"role": "user", "content": _prompt_for(kind, payload)},
            ],
            temperature=0.3,
        )
        text = _extract_chat_text(response)
        if text and text.strip():
            return text.strip()
    except Exception as chat_error:
        if response_error:
            raise RuntimeError(
                f"百炼AI调用失败。Responses错误：{response_error}；Chat回退错误：{chat_error}"
            ) from chat_error
        raise RuntimeError(f"百炼AI调用失败：{chat_error}") from chat_error

    raise RuntimeError("百炼AI返回为空，请检查API Key、地域、模型权限或Base URL")
