from __future__ import annotations
from analytics import student_snapshot


def diagnosis_report(data: dict, student: dict) -> str:
    snap = student_snapshot(data, student["student_id"])
    name = student.get("display_name", "学生")
    target = float(student.get("target_score", 0) or 0)
    weak = [x.get("知识点") for x in snap["weaknesses"][:3]]
    strong = [x.get("知识点") for x in snap["strengths"][:2]]
    errors = snap["error_distribution"]
    main_error = errors[0].get("失分原因") if errors else "暂无明显单一错误类型"
    conf = snap["confidence"]
    trend = "基本稳定"
    if snap["delta_previous"] >= 3:
        trend = "近期明显上升"
    elif snap["delta_previous"] <= -3:
        trend = "近期出现回落"
    return f"""# {name} 学情诊断报告

## 一句话结论
当前综合得分率约 **{snap['latest_percent']:.1f}%**，目标成绩约 **{target:.0f} 分**，整体表现 **{trend}**。现阶段优先级最高的是 **{'、'.join(weak) if weak else '核心薄弱模块'}**。

> 数据置信度：**{conf['level']}**（{conf['exam_count']} 次考试 / {conf['question_count']} 道题）。样本越多，诊断越可靠。

## 学习趋势
- 最近一次得分率：**{snap['latest_percent']:.1f}%**
- 相比上一次：**{snap['delta_previous']:+.1f} 个百分点**
- 相比首次记录：**{snap['delta_first']:+.1f} 个百分点**

## 优势模块
- {'、'.join(strong) if strong else '暂无足够数据'}

## 重点薄弱
- {'、'.join(weak) if weak else '暂无明显薄弱点'}

## 主要失分原因
当前最突出的失分类型是 **{main_error}**。后续复盘应同时记录“错在哪一步”和“为什么会错”，避免只记录答案。

## 可改善失分量（估算）
按当前题目样本与薄弱模块结构估算，若主要薄弱点逐步提升到约75%的掌握水平，涉及约 **{snap['improvement_opportunity_points']:.1f} 分** 的可改善失分量。**这不是成绩承诺，也不代表一定能提高同等分数。**

## 教师建议
1. 对前三个薄弱点分别用3～5道诊断题判断：知识记忆、模型识别、受力过程、临界条件还是计算执行问题。
2. 采用“典型例题拆解 → 变式训练 → 限时小测 → 错因复盘”的闭环，不盲目增加题量。
3. 同类题正确率稳定后再进入下一模块；若错误原因从“知识漏洞”转为“模型识别”，应同步调整教学方式。
"""


def parent_report(data: dict, student: dict) -> str:
    snap = student_snapshot(data, student["student_id"])
    name = student.get("display_name", "学生")
    weak = [x.get("知识点") for x in snap["weaknesses"][:3]]
    strong = [x.get("知识点") for x in snap["strengths"][:2]]
    main_error = snap["error_distribution"][0].get("失分原因") if snap["error_distribution"] else "综合性问题"
    trend_text = "保持稳定"
    if snap["delta_previous"] >= 3:
        trend_text = "呈现上升趋势"
    elif snap["delta_previous"] <= -3:
        trend_text = "近期有一定回落，需要及时调整"
    return f"""# {name} 阶段学情沟通报告（家长版）

## 本阶段表现
最近一次物理得分率约 **{snap['latest_percent']:.1f}%**，相比上一次变化 **{snap['delta_previous']:+.1f} 个百分点**，整体表现 **{trend_text}**。

## 已经形成的优势
目前相对稳定的模块是：**{'、'.join(strong) if strong else '仍需更多数据确认'}**。

## 当前最需要解决的问题
现阶段不建议单纯增加刷题量。更值得集中解决的是：**{'、'.join(weak) if weak else '核心基础与模型应用'}**。

从错误结构看，当前最突出的类型是 **{main_error}**。这意味着后续教学不仅要解决“知识会不会”，还要关注学生是否能够独立识别题型、建立模型并稳定完成解题过程。

## 下一阶段教学安排
- 优先集中训练2～3个薄弱模块，而不是平均用力。
- 每个模块先做诊断题，再进行针对性讲解和变式训练。
- 一周后用同类小测复查，如果正确率稳定提升再进入下一模块。
- 继续保留优势模块的少量维护练习，防止遗忘。

## 关于提升空间
当前数据中约有 **{snap['improvement_opportunity_points']:.1f} 分** 的失分与主要薄弱模块有关，可作为下一阶段教学优先级参考。**这只是对可改善失分结构的估算，不是提分承诺。**

> 本报告基于当前已录入的 {snap['confidence']['exam_count']} 次考试、{snap['confidence']['question_count']} 道题，数据置信度为“{snap['confidence']['level']}”。
"""


def weekly_teaching_plan(data: dict, student: dict) -> str:
    snap = student_snapshot(data, student["student_id"])
    name = student.get("display_name", "学生")
    weak = [x.get("知识点") for x in snap["weaknesses"][:3]] or ["基础知识", "典型模型", "综合应用"]
    while len(weak) < 3:
        weak.append("综合应用")
    return f"""# {name} 本周教学任务

## 本周主目标
围绕 **{weak[0]}** 建立稳定模型识别流程，同时辅助处理 **{weak[1]}**。

## 第1课：诊断 + 纠错
- 3～5道诊断题，确认主要错误发生在知识、模型、受力、临界还是计算。
- 讲解2道典型例题，要求学生口述“为什么用这个模型”。
- 课后：4～6道同类基础变式。

## 第2课：变式 + 迁移
- 主攻：**{weak[0]} / {weak[1]}**。
- 进行“条件变化—模型是否变化”的对比训练。
- 加入1～2道限时题，记录完成时间和错误步骤。

## 第3课/周测：闭环检测
- 20～30分钟专题小测。
- 进入下一模块标准：核心题型正确率 ≥75%，且同类错误不连续重复出现。
- 未达标则保留本模块，下周继续针对错误原因处理，而不是简单重复刷题。

## 本周观察指标
- 题型识别是否更快；
- 错误原因是否从“不会”转为“计算/表达”等低层级问题；
- 是否能独立说出受力对象、过程阶段和关键临界条件。
"""


def plan_30_days(data: dict, student: dict) -> str:
    snap = student_snapshot(data, student["student_id"])
    name = student.get("display_name", "学生")
    topics = [w.get("知识点") for w in snap["weaknesses"][:3]] or ["基础知识", "典型模型", "综合应用"]
    while len(topics) < 3:
        topics.append("综合应用")
    return f"""# {name} 30天物理提升方案

## 第1周：诊断与补洞
- 主攻：**{topics[0]}**
- 任务：知识清单梳理、典型例题6～10题、错因分类
- 周末检测：20～30分钟专题小测

## 第2周：模型强化
- 主攻：**{topics[1]}**
- 任务：模型识别训练、条件变化对比、同题多变式
- 每天安排：30分钟精练 + 10分钟复盘

## 第3周：迁移与综合
- 主攻：**{topics[2]}**
- 任务：跨知识点组合题、限时训练、规范表达
- 目标：把“会做”升级为“能稳定做对”

## 第4周：回测与固化
- 重做本月错题
- 进行2次综合小测
- 对照第1周数据重新计算知识点掌握度和失分结构
- 只保留仍反复出错的2～3类问题进入下一个周期

> 当前数据置信度：{snap['confidence']['level']}。方案应结合学校教学进度动态调整。
"""
