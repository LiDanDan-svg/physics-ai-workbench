from __future__ import annotations
from typing import Dict, List, Tuple, Any
import pandas as pd

SKILLS = ["基础知识", "模型识别", "受力分析", "数学处理", "临界判断", "综合迁移"]
ERROR_TYPES = ["无", "知识漏洞", "模型识别", "受力分析", "审题", "计算", "临界判断", "综合迁移", "其他"]


def student_questions(data: dict, student_id: str) -> pd.DataFrame:
    rows = [q for q in data.get("questions", []) if q.get("student_id") == student_id]
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    for c in ["score", "max_score", "difficulty"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    return df


def student_exams(data: dict, student_id: str) -> pd.DataFrame:
    rows = [e for e in data.get("exams", []) if e.get("student_id") == student_id]
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    for c in ["total_score", "max_score"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    df["percent"] = (df["total_score"] / df["max_score"].replace(0, pd.NA) * 100).fillna(0)
    return df.sort_values("date") if "date" in df.columns else df


def mastery_by_topic(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["知识点", "掌握度", "失分", "题数"])
    tmp = df.copy()
    tmp["lost"] = (tmp["max_score"] - tmp["score"]).clip(lower=0)
    g = tmp.groupby("topic", dropna=False).agg(
        score=("score", "sum"), max_score=("max_score", "sum"), lost=("lost", "sum"), count=("topic", "size")
    ).reset_index()
    g["掌握度"] = (g["score"] / g["max_score"].replace(0, pd.NA) * 100).fillna(0).round(1)
    g = g.rename(columns={"topic": "知识点", "lost": "失分", "count": "题数"})
    return g[["知识点", "掌握度", "失分", "题数"]].sort_values(["掌握度", "失分"], ascending=[True, False])


def error_distribution(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["失分原因", "失分", "占比"])
    tmp = df.copy()
    tmp["lost"] = (tmp["max_score"] - tmp["score"]).clip(lower=0)
    tmp = tmp[tmp["lost"] > 0]
    if tmp.empty:
        return pd.DataFrame(columns=["失分原因", "失分", "占比"])
    g = tmp.groupby("error_type")["lost"].sum().reset_index()
    total = g["lost"].sum()
    g["占比"] = (g["lost"] / total * 100).round(1) if total else 0
    return g.rename(columns={"error_type": "失分原因", "lost": "失分"}).sort_values("失分", ascending=False)


def skill_scores(df: pd.DataFrame) -> Dict[str, float]:
    scores = {s: 60.0 for s in SKILLS}
    if df.empty:
        return scores
    for skill in SKILLS:
        sub = df[df["skill"].astype(str) == skill] if "skill" in df.columns else pd.DataFrame()
        if not sub.empty and sub["max_score"].sum() > 0:
            scores[skill] = round(float(sub["score"].sum() / sub["max_score"].sum() * 100), 1)
    return scores


def latest_score_summary(data: dict, student_id: str) -> Tuple[float, float, float]:
    exams = student_exams(data, student_id)
    if exams.empty:
        return 0.0, 0.0, 0.0
    latest = float(exams.iloc[-1]["percent"])
    prev = float(exams.iloc[-2]["percent"]) if len(exams) >= 2 else latest
    first = float(exams.iloc[0]["percent"])
    return latest, latest - prev, latest - first


def priority_weaknesses(df: pd.DataFrame, top_n: int = 3) -> List[dict]:
    topics = mastery_by_topic(df)
    if topics.empty:
        return []
    rows = topics.copy()
    rows["priority"] = (100 - rows["掌握度"]) * 0.7 + rows["失分"] * 2.0
    return rows.sort_values("priority", ascending=False).head(top_n).to_dict("records")


def improvement_opportunity(df: pd.DataFrame, target_mastery: float = 75) -> float:
    """估算可改善失分量，仅作教学优先级，不等同于承诺提分。"""
    topics = mastery_by_topic(df)
    if topics.empty:
        return 0.0
    recoverable = 0.0
    for _, r in topics.iterrows():
        m = float(r["掌握度"])
        lost = float(r["失分"])
        if m < target_mastery:
            recover_ratio = min(0.65, max(0.15, (target_mastery - m) / 100 + 0.20))
            recoverable += lost * recover_ratio
    return round(recoverable, 1)


def exam_topic_mastery(data: dict, student_id: str) -> pd.DataFrame:
    q = student_questions(data, student_id)
    if q.empty:
        return pd.DataFrame(columns=["exam_id", "知识点", "掌握度", "题数"])
    rows = []
    for eid, sub in q.groupby("exam_id"):
        m = mastery_by_topic(sub)
        for _, r in m.iterrows():
            rows.append({"exam_id": eid, "知识点": r["知识点"], "掌握度": r["掌握度"], "题数": r["题数"]})
    return pd.DataFrame(rows)


def longitudinal_topic_changes(data: dict, student_id: str, top_n: int = 8) -> pd.DataFrame:
    etm = exam_topic_mastery(data, student_id)
    exams = student_exams(data, student_id)
    if etm.empty or exams.empty:
        return pd.DataFrame(columns=["知识点", "首次掌握度", "最近掌握度", "变化"])
    order = {row.exam_id: i for i, row in enumerate(exams.itertuples())}
    etm["_order"] = etm["exam_id"].map(order).fillna(9999)
    rows = []
    for topic, sub in etm.sort_values("_order").groupby("知识点"):
        first = float(sub.iloc[0]["掌握度"])
        latest = float(sub.iloc[-1]["掌握度"])
        rows.append({"知识点": topic, "首次掌握度": first, "最近掌握度": latest, "变化": round(latest-first, 1), "出现次数": len(sub)})
    return pd.DataFrame(rows).sort_values(["最近掌握度", "变化"]).head(top_n)


def evidence_confidence(data: dict, student_id: str) -> dict:
    exams = student_exams(data, student_id)
    q = student_questions(data, student_id)
    n_exam, n_q = len(exams), len(q)
    if n_exam >= 5 and n_q >= 50:
        level, score = "高", 0.85
    elif n_exam >= 3 and n_q >= 20:
        level, score = "中", 0.65
    else:
        level, score = "低", 0.40
    return {"level": level, "score": score, "exam_count": n_exam, "question_count": n_q}


def student_snapshot(data: dict, student_id: str) -> Dict[str, Any]:
    qdf = student_questions(data, student_id)
    edf = student_exams(data, student_id)
    latest, dprev, dfirst = latest_score_summary(data, student_id)
    topics = mastery_by_topic(qdf)
    errors = error_distribution(qdf)
    weak = priority_weaknesses(qdf, 4)
    strong = topics.sort_values("掌握度", ascending=False).head(3).to_dict("records") if not topics.empty else []
    long_df = longitudinal_topic_changes(data, student_id, 10)
    exam_rows = []
    if not edf.empty:
        for _, r in edf.iterrows():
            exam_rows.append({
                "exam_id": str(r.get("exam_id", "")),
                "exam_name": str(r.get("exam_name", "")),
                "date": str(r.get("date", ""))[:10],
                "score": float(r.get("total_score", 0)),
                "max_score": float(r.get("max_score", 0)),
                "percent": round(float(r.get("percent", 0)), 1),
            })
    return {
        "latest_percent": round(latest, 1),
        "delta_previous": round(dprev, 1),
        "delta_first": round(dfirst, 1),
        "exam_history": exam_rows,
        "topic_mastery": topics.to_dict("records") if not topics.empty else [],
        "weaknesses": weak,
        "strengths": strong,
        "error_distribution": errors.to_dict("records") if not errors.empty else [],
        "skill_scores": skill_scores(qdf),
        "longitudinal_topic_changes": long_df.to_dict("records") if not long_df.empty else [],
        "improvement_opportunity_points": improvement_opportunity(qdf),
        "confidence": evidence_confidence(data, student_id),
    }
