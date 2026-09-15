from __future__ import annotations
from collections import defaultdict
from typing import Dict, List, Tuple
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
    g = tmp.groupby("topic", dropna=False).agg(score=("score", "sum"), max_score=("max_score", "sum"), lost=("lost", "sum"), count=("topic", "size")).reset_index()
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
        sub = df[df.get("skill", "").astype(str) == skill] if "skill" in df.columns else pd.DataFrame()
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


def estimate_gain(df: pd.DataFrame, target_mastery: float = 75) -> float:
    topics = mastery_by_topic(df)
    if topics.empty:
        return 0.0
    recoverable = 0.0
    for _, r in topics.iterrows():
        m = float(r["掌握度"])
        lost = float(r["失分"])
        if m < target_mastery:
            recover_ratio = min(0.7, max(0.2, (target_mastery - m) / 100 + 0.25))
            recoverable += lost * recover_ratio
    return round(recoverable, 1)
