from __future__ import annotations
import io, json, uuid
from datetime import date
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from storage import load_workspace, save_workspace, workspace_bytes, restore_workspace
from sample_data import demo_workspace
from analytics import (
    SKILLS, ERROR_TYPES, student_questions, student_exams, mastery_by_topic,
    error_distribution, skill_scores, latest_score_summary, priority_weaknesses,
)
from reporting import diagnosis_report, plan_30_days

st.set_page_config(page_title="旦旦物理 · AI教学工作台", page_icon="🧠", layout="wide")

APP_VERSION = "1.0.0"

st.markdown("""
<style>
.block-container {padding-top: 1.1rem; padding-bottom: 3rem;}
[data-testid="stMetricValue"] {font-size: 1.7rem;}
.small-note {color:#6b7280;font-size:0.88rem;}
.card {border:1px solid #e5e7eb;border-radius:12px;padding:14px 16px;margin-bottom:10px;}
</style>
""", unsafe_allow_html=True)

if "workspace" not in st.session_state:
    st.session_state.workspace = load_workspace()

data = st.session_state.workspace

def persist():
    save_workspace(st.session_state.workspace)


def student_label(s):
    return f"{s.get('display_name','未命名')} · {s.get('student_id','')} · {s.get('grade','')}"

st.title("🧠 旦旦物理 · AI教学工作台")
st.caption(f"V{APP_VERSION}｜学生档案 · 成绩/题目级数据 · 学情分析 · 智能诊断 · 30天提升方案")
st.info("隐私提示：建议使用学生编号或化名，不要上传身份证号、家庭住址等无关敏感信息。V1.0 为轻量原型，云端部署时请定期下载 JSON 备份。")

with st.sidebar:
    st.header("工作区")
    if not data.get("students"):
        if st.button("✨载入演示数据", use_container_width=True):
            st.session_state.workspace = demo_workspace(); persist(); st.rerun()
    else:
        st.success(f"已录入 {len(data['students'])} 名学生")

    st.subheader("💾 数据备份")
    st.download_button("下载工作区备份(JSON)", data=workspace_bytes(data), file_name="physics_ai_workspace.json", mime="application/json", use_container_width=True)
    up = st.file_uploader("恢复工作区备份(JSON)", type=["json"])
    if up is not None and st.button("♻️恢复这份备份", use_container_width=True):
        try:
            st.session_state.workspace = restore_workspace(up.getvalue()); persist(); st.success("恢复成功"); st.rerun()
        except Exception as e:
            st.error(f"恢复失败：{e}")

    if st.button("载入演示数据（覆盖当前）", use_container_width=True):
        st.session_state.workspace = demo_workspace(); persist(); st.rerun()

    st.caption("V1.1 可升级为 Supabase 云数据库，多设备长期持久化。")

# 顶部总览
students = data.get("students", [])
exams = data.get("exams", [])
questions = data.get("questions", [])
c1,c2,c3,c4 = st.columns(4)
c1.metric("学生", len(students))
c2.metric("考试记录", len(exams))
c3.metric("题目级记录", len(questions))
c4.metric("系统版本", f"V{APP_VERSION}")

tabs = st.tabs(["🏠 总览", "👤 学生管理", "📝 考试与题目", "📊 学情分析", "🤖 智能诊断", "📅 30天方案", "📥 批量导入"])

with tabs[0]:
    st.subheader("教学工作台总览")
    if not students:
        st.warning("当前还没有学生。你可以先去“学生管理”新增学生，或者左侧载入演示数据。")
    else:
        rows=[]
        for s in students:
            latest, delta_prev, delta_first = latest_score_summary(data, s["student_id"])
            qdf = student_questions(data, s["student_id"])
            weak = priority_weaknesses(qdf,2)
            rows.append({"学生":s.get("display_name"),"年级":s.get("grade"),"最近得分率":round(latest,1),"较上次":round(delta_prev,1),"目标分":s.get("target_score",0),"重点薄弱":" / ".join([x["知识点"] for x in weak])})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.caption("建议：先录入一次完整考试的题目级数据，再看学情分析，诊断价值会明显提升。")

with tabs[1]:
    st.subheader("学生档案")
    with st.form("add_student", clear_on_submit=True):
        a,b,c = st.columns(3)
        sid = a.text_input("学生编号", placeholder="例如 S003")
        name = b.text_input("显示名称/化名", placeholder="例如 学生C")
        grade = c.selectbox("年级", ["初一","初二","初三","高一","高二","高三"])
        d,e = st.columns(2)
        school = d.text_input("学校（可选）")
        target = e.number_input("目标成绩", min_value=0.0, max_value=150.0, value=80.0, step=1.0)
        notes = st.text_area("备注", placeholder="例如：计算速度慢，受力分析不稳定")
        ok = st.form_submit_button("新增学生", use_container_width=True)
        if ok:
            if not sid or not name:
                st.error("学生编号和显示名称不能为空")
            elif any(x.get("student_id")==sid for x in data["students"]):
                st.error("学生编号已存在")
            else:
                data["students"].append({"student_id":sid,"display_name":name,"grade":grade,"school":school,"target_score":target,"notes":notes}); persist(); st.success("新增成功"); st.rerun()

    if students:
        st.dataframe(pd.DataFrame(students), use_container_width=True, hide_index=True)
        del_sid = st.selectbox("删除学生", [s["student_id"] for s in students], format_func=lambda x: next(student_label(s) for s in students if s["student_id"]==x))
        if st.button("删除该学生及其全部考试数据", type="secondary"):
            data["students"]=[s for s in data["students"] if s["student_id"]!=del_sid]
            data["exams"]=[e for e in data["exams"] if e["student_id"]!=del_sid]
            data["questions"]=[q for q in data["questions"] if q["student_id"]!=del_sid]
            persist(); st.success("已删除"); st.rerun()

with tabs[2]:
    st.subheader("考试与题目级数据")
    if not students:
        st.warning("请先新增学生")
    else:
        sid = st.selectbox("选择学生", [s["student_id"] for s in students], key="exam_student", format_func=lambda x: next(student_label(s) for s in students if s["student_id"]==x))
        st.markdown("#### 1）新增考试")
        with st.form("add_exam", clear_on_submit=True):
            a,b,c,d = st.columns(4)
            exam_name = a.text_input("考试名称", placeholder="例如 9月月考")
            exam_date = b.date_input("日期", value=date.today())
            total = c.number_input("总得分", min_value=0.0, value=70.0, step=1.0)
            max_total = d.number_input("试卷满分", min_value=1.0, value=100.0, step=1.0)
            if st.form_submit_button("保存考试", use_container_width=True):
                eid = "E" + uuid.uuid4().hex[:8].upper()
                data["exams"].append({"exam_id":eid,"student_id":sid,"exam_name":exam_name or "未命名考试","date":str(exam_date),"total_score":total,"max_score":max_total}); persist(); st.success(f"已保存，考试ID：{eid}"); st.rerun()

        exams_s = [e for e in data["exams"] if e["student_id"]==sid]
        if exams_s:
            st.markdown("#### 2）录入题目")
            eid = st.selectbox("选择考试", [e["exam_id"] for e in exams_s], format_func=lambda x: next(f"{e['exam_name']} · {e['date']} · {e['exam_id']}" for e in exams_s if e['exam_id']==x))
            with st.form("add_question", clear_on_submit=True):
                a,b,c,d = st.columns(4)
                qno = a.number_input("题号", min_value=1, value=1, step=1)
                topic = b.text_input("知识点", placeholder="例如 摩擦力临界")
                diff = c.slider("难度", 1, 5, 3)
                skill = d.selectbox("能力维度", SKILLS)
                e,f,g = st.columns(3)
                max_score = e.number_input("满分", min_value=0.5, value=5.0, step=0.5)
                score = f.number_input("得分", min_value=0.0, value=3.0, step=0.5)
                err = g.selectbox("主要错误原因", ERROR_TYPES)
                if st.form_submit_button("添加题目", use_container_width=True):
                    data["questions"].append({"exam_id":eid,"student_id":sid,"question_no":int(qno),"topic":topic or "未分类","difficulty":int(diff),"score":float(score),"max_score":float(max_score),"error_type":err,"skill":skill}); persist(); st.success("题目已添加"); st.rerun()
            qrows=[q for q in data["questions"] if q["exam_id"]==eid]
            if qrows:
                st.dataframe(pd.DataFrame(qrows), use_container_width=True, hide_index=True)
        else:
            st.info("该学生还没有考试记录。")

with tabs[3]:
    st.subheader("学情分析")
    if not students:
        st.warning("请先新增学生")
    else:
        sid = st.selectbox("选择学生", [s["student_id"] for s in students], key="analysis_student", format_func=lambda x: next(student_label(s) for s in students if s["student_id"]==x))
        s = next(x for x in students if x["student_id"]==sid)
        qdf = student_questions(data, sid); edf = student_exams(data, sid)
        latest, dprev, dfirst = latest_score_summary(data, sid)
        a,b,c,d = st.columns(4)
        a.metric("最近得分率", f"{latest:.1f}%")
        b.metric("较上次", f"{dprev:+.1f}")
        c.metric("目标成绩", f"{s.get('target_score',0):.0f}")
        d.metric("题目样本", len(qdf))
        if not edf.empty:
            fig = px.line(edf, x="date", y="percent", markers=True, title="成绩趋势（得分率）")
            fig.update_yaxes(range=[0,100], title="得分率%")
            st.plotly_chart(fig, use_container_width=True)
        if qdf.empty:
            st.info("暂无题目级数据。")
        else:
            left,right = st.columns(2)
            topics = mastery_by_topic(qdf)
            left.markdown("#### 知识点掌握度")
            left.dataframe(topics, use_container_width=True, hide_index=True)
            errors = error_distribution(qdf)
            right.markdown("#### 失分原因")
            if not errors.empty:
                fig2 = px.pie(errors, names="失分原因", values="失分", hole=.45)
                right.plotly_chart(fig2, use_container_width=True)
            skills = skill_scores(qdf)
            radar = go.Figure(data=go.Scatterpolar(r=list(skills.values()), theta=list(skills.keys()), fill="toself"))
            radar.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0,100])), showlegend=False, title="能力雷达")
            st.plotly_chart(radar, use_container_width=True)

with tabs[4]:
    st.subheader("智能学情诊断")
    if not students:
        st.warning("请先新增学生")
    else:
        sid = st.selectbox("选择学生", [s["student_id"] for s in students], key="diag_student", format_func=lambda x: next(student_label(s) for s in students if s["student_id"]==x))
        s = next(x for x in students if x["student_id"]==sid)
        report = diagnosis_report(data, sid, s["display_name"], s.get("target_score"))
        st.markdown(report)
        st.download_button("下载诊断报告(Markdown)", report.encode("utf-8"), file_name=f"{s['display_name']}_学情诊断.md", mime="text/markdown")
        st.caption("V1.0 使用可解释规则引擎生成诊断；下一版可接入大模型，对教师备注、错题文本和试卷内容做更深层分析。")

with tabs[5]:
    st.subheader("30天提升方案")
    if not students:
        st.warning("请先新增学生")
    else:
        sid = st.selectbox("选择学生", [s["student_id"] for s in students], key="plan_student", format_func=lambda x: next(student_label(s) for s in students if s["student_id"]==x))
        s = next(x for x in students if x["student_id"]==sid)
        plan = plan_30_days(data, sid, s["display_name"])
        st.markdown(plan)
        st.download_button("下载30天方案(Markdown)", plan.encode("utf-8"), file_name=f"{s['display_name']}_30天提升方案.md", mime="text/markdown")

with tabs[6]:
    st.subheader("批量导入")
    st.write("适合一次性导入班级学生、考试或题目级数据。")
    st.markdown("#### 学生CSV")
    st.code("student_id,display_name,grade,school,target_score,notes")
    sf = st.file_uploader("上传学生CSV", type=["csv"], key="students_csv")
    if sf is not None and st.button("导入学生CSV"):
        try:
            df = pd.read_csv(sf)
            required={"student_id","display_name","grade"}
            if not required.issubset(df.columns):
                st.error(f"缺少字段：{required-set(df.columns)}")
            else:
                existing={s["student_id"] for s in data["students"]}
                n=0
                for _,r in df.iterrows():
                    sid=str(r["student_id"])
                    if sid in existing: continue
                    data["students"].append({"student_id":sid,"display_name":str(r["display_name"]),"grade":str(r["grade"]),"school":str(r.get("school","")),"target_score":float(r.get("target_score",80) or 80),"notes":str(r.get("notes",""))}); existing.add(sid); n+=1
                persist(); st.success(f"导入 {n} 名学生"); st.rerun()
        except Exception as e: st.error(str(e))

    st.markdown("#### 题目级CSV")
    st.code("exam_id,student_id,question_no,topic,difficulty,score,max_score,error_type,skill")
    qf = st.file_uploader("上传题目级CSV", type=["csv"], key="questions_csv")
    if qf is not None and st.button("导入题目级CSV"):
        try:
            df=pd.read_csv(qf)
            req={"exam_id","student_id","question_no","topic","score","max_score"}
            if not req.issubset(df.columns): st.error(f"缺少字段：{req-set(df.columns)}")
            else:
                for _,r in df.iterrows():
                    data["questions"].append({
                        "exam_id":str(r["exam_id"]),"student_id":str(r["student_id"]),"question_no":int(r["question_no"]),"topic":str(r["topic"]),
                        "difficulty":int(r.get("difficulty",3) or 3),"score":float(r["score"]),"max_score":float(r["max_score"]),
                        "error_type":str(r.get("error_type","其他")),"skill":str(r.get("skill","基础知识"))})
                persist(); st.success(f"导入 {len(df)} 条题目数据"); st.rerun()
        except Exception as e: st.error(str(e))
