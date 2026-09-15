from __future__ import annotations

import base64
import json
import re
from typing import Any, Dict, Iterable, List, Sequence

DEFAULT_VISION_MODEL = "qwen3.8-flash"

PHYSICS_SKILLS = ["基础知识", "模型识别", "受力分析", "数学处理", "临界判断", "综合迁移"]
ERROR_TYPES = ["无", "知识漏洞", "模型识别", "受力分析", "审题", "计算", "临界判断", "综合迁移", "其他"]

PAPER_SYSTEM = """你是高中物理教师的试卷结构化助手。请读取教师上传的物理试卷/答题纸，并输出可核对的结构化题目数据。
要求：
1. 只提取文件中能确认的信息；看不清就标记 unknown，不要猜题号、分值或答案。
2. 每个题目给出：题号、简短题意摘要、主要知识点、能力维度、难度1-5、满分、题型、参考答案/关键结论（若可可靠判断）、典型易错点。
3. 如果画面中明确能看到老师批改后的学生得分，可填 student_score；不明确时必须为 null。
4. 知识点使用高中物理常见中文名称，例如：运动学、受力分析、摩擦力临界、牛顿第二定律、圆周运动、万有引力、功和能、动量、电场、电路、磁场、电磁感应、机械振动与波、光学、近代物理等。
5. 能力维度只能从：基础知识、模型识别、受力分析、数学处理、临界判断、综合迁移 中选择。
6. 不需要复述长篇原题，只保留足以教学分析的题意摘要。
7. 输出严格 JSON，不要输出 Markdown 代码块。
"""


def _data_uri(file_bytes: bytes, mime: str) -> str:
    return f"data:{mime};base64,{base64.b64encode(file_bytes).decode('ascii')}"


def _extract_json(text: str) -> Any:
    text = (text or "").strip()
    if not text:
        raise ValueError("AI返回为空")
    # 先尝试直接解析
    try:
        return json.loads(text)
    except Exception:
        pass
    # 去掉常见 markdown fence
    cleaned = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except Exception:
        pass
    # 最后截取最外层 JSON 对象/数组
    candidates = []
    for left, right in [("{", "}"), ("[", "]")]:
        a, b = cleaned.find(left), cleaned.rfind(right)
        if a >= 0 and b > a:
            candidates.append(cleaned[a:b+1])
    for c in candidates:
        try:
            return json.loads(c)
        except Exception:
            continue
    raise ValueError("AI返回内容不是可解析的JSON")


def _num(v, default=0.0):
    if v is None or v == "":
        return default
    try:
        return float(v)
    except Exception:
        return default


def normalize_question_rows(obj: Any) -> Dict[str, Any]:
    if isinstance(obj, list):
        obj = {"questions": obj}
    if not isinstance(obj, dict):
        raise ValueError("试卷解析结果不是JSON对象")
    rows = obj.get("questions") or obj.get("items") or []
    if not isinstance(rows, list):
        rows = []
    out: List[Dict[str, Any]] = []
    for i, q in enumerate(rows, start=1):
        if not isinstance(q, dict):
            continue
        qno = q.get("question_no", q.get("no", i))
        try:
            qno = int(float(qno))
        except Exception:
            qno = i
        skill = str(q.get("skill") or "模型识别").strip()
        if skill not in PHYSICS_SKILLS:
            skill = "模型识别"
        difficulty = int(max(1, min(5, round(_num(q.get("difficulty"), 3)))))
        max_score = max(0.0, _num(q.get("max_score"), 0.0))
        ss = q.get("student_score")
        student_score = None if ss in (None, "", "unknown", "未知") else max(0.0, _num(ss, 0.0))
        if student_score is not None and max_score > 0:
            student_score = min(student_score, max_score)
        out.append({
            "question_no": qno,
            "stem_summary": str(q.get("stem_summary") or q.get("summary") or "").strip(),
            "topic": str(q.get("topic") or "未分类").strip() or "未分类",
            "skill": skill,
            "difficulty": difficulty,
            "max_score": max_score,
            "student_score": student_score,
            "question_type": str(q.get("question_type") or q.get("type") or "未分类").strip(),
            "reference_answer": str(q.get("reference_answer") or q.get("answer") or "").strip(),
            "common_trap": str(q.get("common_trap") or q.get("mistake") or "").strip(),
            "error_type": "无" if student_score is not None and max_score > 0 and student_score >= max_score else "其他",
            "note": "",
        })
    return {
        "paper_title": str(obj.get("paper_title") or obj.get("title") or "AI解析试卷").strip(),
        "subject": str(obj.get("subject") or "物理").strip(),
        "grade": str(obj.get("grade") or "").strip(),
        "total_score": _num(obj.get("total_score"), sum(r["max_score"] for r in out)),
        "questions": sorted(out, key=lambda x: x["question_no"]),
        "warnings": obj.get("warnings") if isinstance(obj.get("warnings"), list) else [],
    }


def _instruction(extra_instruction: str = "") -> str:
    extra = f"\n教师补充要求：{extra_instruction.strip()}" if extra_instruction and extra_instruction.strip() else ""
    return PAPER_SYSTEM + extra + """

请按以下JSON结构返回：
{
  "paper_title":"",
  "subject":"物理",
  "grade":"",
  "total_score":100,
  "warnings":[],
  "questions":[
    {
      "question_no":1,
      "stem_summary":"不超过80字的题意摘要",
      "topic":"知识点",
      "skill":"模型识别",
      "difficulty":3,
      "max_score":5,
      "student_score":null,
      "question_type":"选择/填空/计算/实验/其他",
      "reference_answer":"可可靠判断时填写，否则留空",
      "common_trap":"典型易错点"
    }
  ]
}
"""


def parse_paper_files(
    uploaded_files: Sequence[Dict[str, Any]],
    api_key: str,
    base_url: str,
    model: str = DEFAULT_VISION_MODEL,
    extra_instruction: str = "",
) -> Dict[str, Any]:
    """uploaded_files: [{name, mime, bytes}]。PDF与图片分别按百炼OpenAI兼容协议传入。"""
    from openai import OpenAI

    if not api_key:
        raise RuntimeError("未配置 DASHSCOPE_API_KEY")
    if not uploaded_files:
        raise ValueError("请先上传试卷PDF或图片")

    client = OpenAI(api_key=api_key.strip(), base_url=base_url.strip())
    content: List[Dict[str, Any]] = [{"type": "text", "text": _instruction(extra_instruction)}]

    pdf_count = 0
    image_count = 0
    for f in uploaded_files:
        name = str(f.get("name") or "upload")
        mime = str(f.get("mime") or "application/octet-stream").lower()
        b = f.get("bytes") or b""
        if not isinstance(b, (bytes, bytearray)):
            continue
        if mime == "application/pdf" or name.lower().endswith(".pdf"):
            pdf_count += 1
            if pdf_count > 1:
                raise ValueError("一次解析最多上传1个PDF；多份试卷请分开解析。")
            content.append({
                "type": "file",
                "file": {
                    "file_data": _data_uri(bytes(b), "application/pdf"),
                    "filename": name,
                },
            })
        elif mime.startswith("image/") or name.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
            image_count += 1
            if image_count > 8:
                raise ValueError("一次最多上传8张图片。")
            if not mime.startswith("image/"):
                mime = "image/jpeg"
            content.append({
                "type": "image_url",
                "image_url": {"url": _data_uri(bytes(b), mime)},
            })
        else:
            raise ValueError(f"不支持的文件类型：{name}")

    # PDF理解当前通过 Chat Completions 传入；图片同样统一走 Chat，便于混合输入。
    completion = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": content}],
        temperature=0.1,
    )
    text = completion.choices[0].message.content or ""
    parsed = normalize_question_rows(_extract_json(text))
    parsed["source_files"] = [str(f.get("name") or "upload") for f in uploaded_files]
    parsed["model"] = model
    return parsed
