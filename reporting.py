from __future__ import annotations
from typing import List
from analytics import latest_score_summary, mastery_by_topic, error_distribution, priority_weaknesses, estimate_gain, student_questions


def diagnosis_report(data: dict, student_id: str, student_name: str, target_score: float | None = None) -> str:
    qdf = student_questions(data, student_id)
    latest, delta_prev, delta_first = latest_score_summary(data, student_id)
    topics = mastery_by_topic(qdf)
    errors = error_distribution(qdf)
    weaknesses = priority_weaknesses(qdf, 3)
    gain = estimate_gain(qdf)

    if qdf.empty:
        return f"# {student_name} 学情诊断\n\n暂无题目级数据，请先录入考试和题目得分。"

    strong = topics.sort_values("掌握度", ascending=False).head(2)["知识点"].tolist() if not topics.empty else []
    weak = [w["知识点"] for w in weaknesses]
    main_error = errors.iloc[0]["失分原因"] if not errors.empty else "暂无明显单一错误类型"
    target_text = f"，目标成绩约 {target_score:.0f} 分" if target_score else ""

    trend = "基本稳定"
    if delta_prev >= 3:
        trend = "近期明显上升"
    elif delta_prev <= -3:
        trend = "近期出现回落"

    return f"""# {student_name} 学情诊断报告

## 一句话结论
当前综合得分率约 **{latest:.1f}%**{target_text}，整体表现 **{trend}**。现阶段最值得优先解决的不是盲目刷题，而是集中处理 **{'、'.join(weak) if weak else '核心薄弱模块'}**。

## 学习趋势
- 最近一次得分率：**{latest:.1f}%**
- 相比上一次：**{delta_prev:+.1f} 个百分点**
- 相比首次记录：**{delta_first:+.1f} 个百分点**

## 优势模块
- {'、'.join(strong) if strong else '暂无足够数据'}

## 重点薄弱
- {'、'.join(weak) if weak else '暂无明显薄弱点'}

## 主要失分原因
当前最突出的失分类型是 **{main_error}**。建议后续训练时不要只看“这题会不会”，还要记录“为什么错”。

## 预计提分空间
按现有题目结构粗略测算，如果前三个薄弱模块提升到约75%的掌握度，理论上可减少约 **{gain:.1f} 分** 的失分。这个数字只用于制定学习优先级，不代表成绩承诺。

## 教师建议
1. 先用 3～5 道典型题确认薄弱点究竟是知识记忆、模型识别还是计算执行问题。
2. 每个薄弱模块采用“例题拆解 → 变式训练 → 限时小测 → 错因复盘”四步闭环。
3. 训练后重新测同类题，只有正确率稳定提升才进入下一模块。
"""


def plan_30_days(data: dict, student_id: str, student_name: str) -> str:
    qdf = student_questions(data, student_id)
    weaknesses = priority_weaknesses(qdf, 3)
    topics = [w["知识点"] for w in weaknesses] or ["基础知识", "典型模型", "综合应用"]
    while len(topics) < 3:
        topics.append("综合应用")
    return f"""# {student_name} 30天物理提升方案

## 第1周：诊断与补洞
- 主攻：**{topics[0]}**
- 任务：知识清单梳理、典型例题6～10题、错因分类
- 周末检测：20～30分钟专题小测

## 第2周：模型强化
- 主攻：**{topics[1]}**
- 任务：模型识别训练、同题多解、易错条件对比
- 每天安排：30分钟精练 + 10分钟复盘

## 第3周：迁移与综合
- 主攻：**{topics[2]}**
- 任务：跨知识点组合题、限时训练、规范表达
- 目标：把“会做”升级为“能稳定做对”

## 第4周：回测与固化
- 重做本月错题
- 进行2次综合小测
- 对照第1周数据重新计算知识点掌握度和失分结构
- 只保留仍然反复出错的2～3类问题进入下一个周期

> 本方案用于教学规划，应结合学生实际课内进度与学校考试安排动态调整。
"""
