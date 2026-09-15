from __future__ import annotations
import uuid
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
    longitudinal_topic_changes, student_snapshot,
)
from reporting import diagnosis_report, parent_report, weekly_teaching_plan, plan_30_days
from ai_engine import ai_configured, generate_ai_report, ai_payload_preview, DEFAULT_DASHSCOPE_BASE_URL, DEFAULT_QWEN_MODEL

st.set_page_config(page_title="旦旦物理 · AI教学工作台", page_icon="🧠", layout="wide")
APP_VERSION = "1.1.1"

st.markdown("""
<style>
.block-container {padding-top: 1.0rem; padding-bottom: 3rem;}
[data-testid="stMetricValue"] {font-size: 1.7rem;}
.small-note {color:#6b7280;font-size:0.88rem;}
.status-card {border:1px solid #e5e7eb;border-radius:12px;padding:12px 14px;margin-bottom:8px;}
</style>
""", unsafe_allow_html=True)


def secret(name: str, default=""):
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default

SUPABASE_URL = str(secret("SUPABASE_URL", "")).strip()
SUPABASE_KEY = str(secret("SUPABASE_PUBLISHABLE_KEY", "")).strip()
ALLOWED_EMAIL = str(secret("ALLOWED_TEACHER_EMAIL", "")).strip().lower()
DASHSCOPE_API_KEY = str(secret("DASHSCOPE_API_KEY", "")).strip()
QWEN_MODEL = str(secret("QWEN_MODEL", DEFAULT_QWEN_MODEL)).strip() or DEFAULT_QWEN_MODEL
DASHSCOPE_BASE_URL = str(secret("DASHSCOPE_BASE_URL", DEFAULT_DASHSCOPE_BASE_URL)).strip() or DEFAULT_DASHSCOPE_BASE_URL
CLOUD_MODE = bool(SUPABASE_URL and SUPABASE_KEY)
AI_READY = ai_configured(DASHSCOPE_API_KEY)
AI_PROVIDER_LABEL = f"阿里云百炼 · {QWEN_MODEL}"


def cloud_login_gate():
    from cloud_store import create_supabase_client, sign_in, sign_up, load_cloud_workspace
    if st.session_state.get("sb_client") and st.session_state.get("teacher_user"):
        return
    st.title("🧠 旦旦物理 · AI教学工作台")
    st.caption(f"V{APP_VERSION}｜教师登录 · 云端学生数据 · 百炼千问AI · 家长报告")
    st.info("当前已启用 Supabase 云端模式。请使用教师账号登录。")
    login_tab, signup_tab = st.tabs(["🔐 教师登录", "🆕 首次创建账号"])
    with login_tab:
        with st.form("login_form"):
            email = st.text_input("邮箱")
            password = st.text_input("密码", type="password")
            submitted = st.form_submit_button("登录", use_container_width=True, type="primary")
        if submitted:
            try:
                client = create_supabase_client(SUPABASE_URL, SUPABASE_KEY)
                user, session = sign_in(client, email.strip(), password)
                if ALLOWED_EMAIL and (getattr(user, "email", "") or "").lower() != ALLOWED_EMAIL:
                    client.auth.sign_out()
                    st.error("该账号不在允许的教师名单中。")
                else:
                    st.session_state.sb_client = client
                    st.session_state.teacher_user = user
                    st.session_state.workspace = load_cloud_workspace(client, user.id)
                    st.rerun()
            except Exception as e:
                st.error(f"登录失败：{e}")
    with signup_tab:
        st.caption("如果 Supabase 开启了邮箱验证，注册后需先到邮箱完成确认。")
        with st.form("signup_form"):
            email2 = st.text_input("注册邮箱")
            pwd2 = st.text_input("设置密码（建议至少8位）", type="password")
            submitted2 = st.form_submit_button("创建教师账号", use_container_width=True)
        if submitted2:
            try:
                client = create_supabase_client(SUPABASE_URL, SUPABASE_KEY)
                user, session = sign_up(client, email2.strip(), pwd2)
                if session and user:
                    if ALLOWED_EMAIL and (getattr(user, "email", "") or "").lower() != ALLOWED_EMAIL:
                        client.auth.sign_out()
                        st.error("该邮箱不在允许的教师名单中。")
                    else:
                        st.session_state.sb_client = client
                        st.session_state.teacher_user = user
                        st.session_state.workspace = load_cloud_workspace(client, user.id)
                        st.success("账号创建成功，正在进入工作台。")
                        st.rerun()
                else:
                    st.success("账号创建成功，请先查收邮箱完成验证，再返回登录。")
            except Exception as e:
                st.error(f"注册失败：{e}")
    st.stop()


if CLOUD_MODE:
    cloud_login_gate()
    data = st.session_state.workspace
else:
    if "workspace" not in st.session_state:
        st.session_state.workspace = load_workspace()
    data = st.session_state.workspace


def persist():
    if CLOUD_MODE:
        from cloud_store import save_cloud_workspace
        user = st.session_state.teacher_user
        save_cloud_workspace(st.session_state.sb_client, user.id, st.session_state.workspace)
    else:
        save_workspace(st.session_state.workspace)


def student_label(s):
    return f"{s.get('display_name','未命名')} · {s.get('student_id','')} · {s.get('grade','')}"


def find_student(sid):
    return next(x for x in data.get("students", []) if x.get("student_id") == sid)


def report_key(kind, sid):
    return f"{kind}:{sid}"


def render_ai_or_rule(kind: str, student: dict, fallback: str):
    key = report_key(kind, student["student_id"])
    saved = data.get("ai_reports", {}).get(key)

    with st.expander("🔎 查看本次发送给AI的数据摘要（隐私预览）", expanded=False):
        preview = ai_payload_preview(data, student)
        st.json(preview)
        st.caption("默认不会把学生显示名称、学校、身份证号、家庭住址等直接识别信息发送给AI。教师备注会发送，请勿在备注中填写无关敏感信息。")

    if AI_READY:
        if st.button("✨ 生成/刷新百炼AI报告", key=f"ai_{kind}_{student['student_id']}", type="primary"):
            try:
                with st.spinner("千问正在读取学情摘要并生成报告..."):
                    text = generate_ai_report(
                        kind, data, student,
                        DASHSCOPE_API_KEY, QWEN_MODEL, DASHSCOPE_BASE_URL
                    )
                data.setdefault("ai_reports", {})[key] = text
                persist(); st.success("百炼AI报告已生成"); st.rerun()
            except Exception as e:
                st.error(f"百炼AI生成失败：{e}")
        if saved:
            st.success(f"当前显示百炼AI报告 · 模型 {QWEN_MODEL}")
            return saved
        st.info("已配置阿里云百炼，但尚未生成该学生的AI报告。下方先显示规则版。")
        return fallback

    st.info("当前未配置阿里云百炼 API，显示可解释规则版。配置后可一键生成千问AI报告。")
    return fallback


st.title("🧠 旦旦物理 · AI教学工作台")
st.caption(f"V{APP_VERSION}｜云端学生档案 · 纵向学情 · 百炼千问AI · 家长报告 · 本周教学任务")
if CLOUD_MODE:
    user_email = getattr(st.session_state.teacher_user, "email", "教师账号")
    st.success(f"☁️ 云端模式已连接 · 当前教师：{user_email}")
else:
    st.warning("当前为本地/原型模式：Streamlit Cloud 重启后本地文件可能丢失。正式录入学生长期数据前，建议完成 Supabase 配置。")
st.info("隐私提示：尽量使用学生编号或化名；不要采集身份证号、家庭住址等与教学无关的敏感信息。AI报告应由老师审核后再对外发送。")

with st.sidebar:
    st.header("工作区")
    if CLOUD_MODE:
        st.success("☁️ Supabase 云数据库")
        if st.button("退出教师账号", use_container_width=True):
            try:
                st.session_state.sb_client.auth.sign_out()
            except Exception:
                pass
            for k in ["sb_client", "teacher_user", "workspace"]:
                st.session_state.pop(k, None)
            st.rerun()
    else:
        st.warning("🧪 本地原型模式")

    if not data.get("students"):
        if st.button("✨ 载入演示数据", use_container_width=True):
            st.session_state.workspace = demo_workspace(); data = st.session_state.workspace; persist(); st.rerun()
    else:
        st.success(f"已录入 {len(data['students'])} 名学生")

    st.subheader("💾 数据备份")
    st.download_button("下载工作区备份(JSON)", data=workspace_bytes(data), file_name="physics_ai_workspace_v11.json", mime="application/json", use_container_width=True)
    up = st.file_uploader("恢复工作区备份(JSON)", type=["json"])
    if up is not None and st.button("♻️ 恢复这份备份", use_container_width=True):
        try:
            st.session_state.workspace = restore_workspace(up.getvalue()); data = st.session_state.workspace; persist(); st.success("恢复成功"); st.rerun()
        except Exception as e:
            st.error(f"恢复失败：{e}")

    if st.button("载入演示数据（覆盖当前）", use_container_width=True):
        st.session_state.workspace = demo_workspace(); data = st.session_state.workspace; persist(); st.rerun()

    st.subheader("🧠 AI状态")
    if AI_READY:
        st.success(f"已连接：{AI_PROVIDER_LABEL}")
    else:
        st.info("未配置阿里云百炼 API，当前使用规则诊断")

students = data.get("students", [])
exams = data.get("exams", [])
questions = data.get("questions", [])
c1,c2,c3,c4 = st.columns(4)
c1.metric("学生", len(students)); c2.metric("考试记录", len(exams)); c3.metric("题目级记录", len(questions)); c4.metric("系统版本", f"V{APP_VERSION}")

tabs = st.tabs(["🏠 总览", "👤 学生管理", "📝 考试与题目", "📊 学情分析", "🧠 AI诊断", "👨‍👩‍👧 家长报告", "📌 本周教学", "📅 30天方案", "📥 批量导入", "⚙️ 系统设置"])

with tabs[0]:
    st.subheader("教学工作台总览")
    if not students:
        st.warning("当前还没有学生。可以先去“学生管理”新增，或左侧载入演示数据。")
    else:
        rows=[]
        for s in students:
            latest, delta_prev, _ = latest_score_summary(data, s["student_id"])
            weak = priority_weaknesses(student_questions(data, s["student_id"]),2)
            conf = student_snapshot(data, s["student_id"])["confidence"]
            rows.append({"学生":s.get("display_name"),"年级":s.get("grade"),"最近得分率":round(latest,1),"较上次":round(delta_prev,1),"目标分":s.get("target_score",0),"重点薄弱":" / ".join([x["知识点"] for x in weak]),"数据置信度":conf["level"]})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.caption("V1.1建议：持续录入同一学生的多次考试，纵向变化比单次分数更有诊断价值。")

with tabs[1]:
    st.subheader("学生档案")
    with st.form("add_student", clear_on_submit=True):
        a,b,c = st.columns(3)
        sid = a.text_input("学生编号", placeholder="例如 S003")
        name = b.text_input("显示名称/化名", placeholder="例如 学生C")
        grade = c.selectbox("年级", ["初一","初二","初三","高一","高二","高三"])
        d,e = st.columns(2)
        school = d.text_input("学校（可选，建议简写）")
        target = e.number_input("目标成绩", min_value=0.0, max_value=150.0, value=80.0, step=1.0)
        notes = st.text_area("教师备注", placeholder="例如：计算速度慢，能听懂但独立建模不稳定")
        ok = st.form_submit_button("新增学生", use_container_width=True)
        if ok:
            if not sid or not name: st.error("学生编号和显示名称不能为空")
            elif any(x.get("student_id")==sid for x in data["students"]): st.error("学生编号已存在")
            else:
                data["students"].append({"student_id":sid,"display_name":name,"grade":grade,"school":school,"target_score":target,"notes":notes}); persist(); st.success("新增成功"); st.rerun()
    if students:
        st.dataframe(pd.DataFrame(students), use_container_width=True, hide_index=True)
        sid_edit = st.selectbox("编辑/删除学生", [s["student_id"] for s in students], key="student_edit", format_func=lambda x: student_label(find_student(x)))
        s0 = find_student(sid_edit)
        with st.form("edit_student"):
            a,b,c = st.columns(3)
            new_name = a.text_input("显示名称", value=s0.get("display_name", ""))
            new_grade = b.selectbox("年级", ["初一","初二","初三","高一","高二","高三"], index=max(0,["初一","初二","初三","高一","高二","高三"].index(s0.get("grade","高一"))))
            new_target = c.number_input("目标成绩", 0.0, 150.0, float(s0.get("target_score",80)), 1.0)
            new_notes = st.text_area("教师备注", value=s0.get("notes", ""))
            if st.form_submit_button("保存修改"):
                s0.update({"display_name":new_name,"grade":new_grade,"target_score":new_target,"notes":new_notes}); persist(); st.success("已保存"); st.rerun()
        if st.button("删除该学生及其全部数据", type="secondary"):
            data["students"]=[s for s in data["students"] if s["student_id"]!=sid_edit]
            data["exams"]=[e for e in data["exams"] if e["student_id"]!=sid_edit]
            data["questions"]=[q for q in data["questions"] if q["student_id"]!=sid_edit]
            for k in list(data.get("ai_reports",{})):
                if k.endswith(f":{sid_edit}"): data["ai_reports"].pop(k,None)
            persist(); st.success("已删除"); st.rerun()

with tabs[2]:
    st.subheader("考试与题目级数据")
    if not students: st.warning("请先新增学生")
    else:
        sid = st.selectbox("选择学生", [s["student_id"] for s in students], key="exam_student", format_func=lambda x: student_label(find_student(x)))
        st.markdown("#### 1）新增考试")
        with st.form("add_exam", clear_on_submit=True):
            a,b,c,d = st.columns(4)
            exam_name = a.text_input("考试名称", placeholder="例如 9月月考")
            exam_date = b.date_input("日期", value=date.today())
            total = c.number_input("总得分", min_value=0.0, value=70.0, step=1.0)
            max_total = d.number_input("试卷满分", min_value=1.0, value=100.0, step=1.0)
            if st.form_submit_button("保存考试", use_container_width=True):
                eid = "E" + uuid.uuid4().hex[:8].upper(); data["exams"].append({"exam_id":eid,"student_id":sid,"exam_name":exam_name or "未命名考试","date":str(exam_date),"total_score":total,"max_score":max_total}); persist(); st.success(f"已保存：{eid}"); st.rerun()
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
                note = st.text_input("错因备注（可选）", placeholder="例如：不知道临界时摩擦力取最大静摩擦力")
                if st.form_submit_button("添加题目", use_container_width=True):
                    data["questions"].append({"exam_id":eid,"student_id":sid,"question_no":int(qno),"topic":topic or "未分类","difficulty":int(diff),"score":float(score),"max_score":float(max_score),"error_type":err,"skill":skill,"note":note}); persist(); st.success("题目已添加"); st.rerun()
            qrows=[q for q in data["questions"] if q["exam_id"]==eid]
            if qrows: st.dataframe(pd.DataFrame(qrows), use_container_width=True, hide_index=True)
        else: st.info("该学生还没有考试记录。")

with tabs[3]:
    st.subheader("学情分析 · 纵向变化")
    if not students: st.warning("请先新增学生")
    else:
        sid = st.selectbox("选择学生", [s["student_id"] for s in students], key="analysis_student", format_func=lambda x: student_label(find_student(x)))
        s = find_student(sid); qdf = student_questions(data, sid); edf = student_exams(data, sid); snap = student_snapshot(data, sid)
        a,b,c,d,e = st.columns(5)
        a.metric("最近得分率", f"{snap['latest_percent']:.1f}%"); b.metric("较上次", f"{snap['delta_previous']:+.1f}"); c.metric("目标成绩", f"{s.get('target_score',0):.0f}"); d.metric("题目样本", snap["confidence"]["question_count"]); e.metric("置信度", snap["confidence"]["level"])
        if not edf.empty:
            fig = px.line(edf, x="date", y="percent", markers=True, title="成绩趋势（得分率）"); fig.update_yaxes(range=[0,100], title="得分率%")
            st.plotly_chart(fig, use_container_width=True)
        if qdf.empty: st.info("暂无题目级数据。")
        else:
            left,right = st.columns(2)
            topics = mastery_by_topic(qdf); left.markdown("#### 知识点掌握度"); left.dataframe(topics, use_container_width=True, hide_index=True)
            errors = error_distribution(qdf); right.markdown("#### 失分原因")
            if not errors.empty: right.plotly_chart(px.pie(errors, names="失分原因", values="失分", hole=.45), use_container_width=True)
            skills = skill_scores(qdf); radar = go.Figure(data=go.Scatterpolar(r=list(skills.values()), theta=list(skills.keys()), fill="toself")); radar.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0,100])), showlegend=False, title="六维能力雷达"); st.plotly_chart(radar, use_container_width=True)
            changes = longitudinal_topic_changes(data, sid, 10)
            st.markdown("#### 知识点纵向变化")
            if not changes.empty: st.dataframe(changes, use_container_width=True, hide_index=True)
            else: st.caption("同一知识点需要至少跨考试出现，才能形成纵向变化。")

with tabs[4]:
    st.subheader("🧠 教师版学情诊断")
    if not students: st.warning("请先新增学生")
    else:
        sid = st.selectbox("选择学生", [s["student_id"] for s in students], key="diag_student", format_func=lambda x: student_label(find_student(x)))
        s = find_student(sid); fallback = diagnosis_report(data, s); text = render_ai_or_rule("diagnosis", s, fallback)
        st.markdown(text); st.download_button("下载教师诊断(Markdown)", text.encode("utf-8"), file_name=f"{sid}_teacher_diagnosis.md", mime="text/markdown")

with tabs[5]:
    st.subheader("👨‍👩‍👧 家长版阶段学情报告")
    if not students: st.warning("请先新增学生")
    else:
        sid = st.selectbox("选择学生", [s["student_id"] for s in students], key="parent_student", format_func=lambda x: student_label(find_student(x)))
        s = find_student(sid); fallback = parent_report(data, s); text = render_ai_or_rule("parent", s, fallback)
        st.markdown(text); st.download_button("下载家长报告(Markdown)", text.encode("utf-8"), file_name=f"{sid}_parent_report.md", mime="text/markdown")
        st.caption("发送给家长前请老师人工审核，删除不必要的技术标签，并确认没有不当承诺。")

with tabs[6]:
    st.subheader("📌 本周教学任务")
    if not students: st.warning("请先新增学生")
    else:
        sid = st.selectbox("选择学生", [s["student_id"] for s in students], key="weekly_student", format_func=lambda x: student_label(find_student(x)))
        s = find_student(sid); fallback = weekly_teaching_plan(data, s); text = render_ai_or_rule("weekly", s, fallback)
        st.markdown(text); st.download_button("下载本周任务(Markdown)", text.encode("utf-8"), file_name=f"{sid}_weekly_plan.md", mime="text/markdown")

with tabs[7]:
    st.subheader("📅 30天提升方案")
    if not students: st.warning("请先新增学生")
    else:
        sid = st.selectbox("选择学生", [s["student_id"] for s in students], key="plan_student", format_func=lambda x: student_label(find_student(x)))
        s = find_student(sid); fallback = plan_30_days(data, s); text = render_ai_or_rule("plan30", s, fallback)
        st.markdown(text); st.download_button("下载30天方案(Markdown)", text.encode("utf-8"), file_name=f"{sid}_30day_plan.md", mime="text/markdown")

with tabs[8]:
    st.subheader("批量导入")
    st.markdown("#### 学生CSV")
    st.code("student_id,display_name,grade,school,target_score,notes")
    sf = st.file_uploader("上传学生CSV", type=["csv"], key="students_csv")
    if sf is not None and st.button("导入学生CSV"):
        try:
            df = pd.read_csv(sf); required={"student_id","display_name","grade"}
            if not required.issubset(df.columns): st.error(f"缺少字段：{required-set(df.columns)}")
            else:
                existing={s["student_id"] for s in data["students"]}; n=0
                for _,r in df.iterrows():
                    sid=str(r["student_id"])
                    if sid in existing: continue
                    data["students"].append({"student_id":sid,"display_name":str(r["display_name"]),"grade":str(r["grade"]),"school":str(r.get("school","")),"target_score":float(r.get("target_score",80) or 80),"notes":str(r.get("notes",""))}); existing.add(sid); n+=1
                persist(); st.success(f"导入 {n} 名学生"); st.rerun()
        except Exception as e: st.error(str(e))
    st.markdown("#### 题目级CSV")
    st.code("exam_id,student_id,question_no,topic,difficulty,score,max_score,error_type,skill,note")
    qf = st.file_uploader("上传题目级CSV", type=["csv"], key="questions_csv")
    if qf is not None and st.button("导入题目级CSV"):
        try:
            df=pd.read_csv(qf); req={"exam_id","student_id","question_no","topic","score","max_score"}
            if not req.issubset(df.columns): st.error(f"缺少字段：{req-set(df.columns)}")
            else:
                for _,r in df.iterrows():
                    data["questions"].append({"exam_id":str(r["exam_id"]),"student_id":str(r["student_id"]),"question_no":int(r["question_no"]),"topic":str(r["topic"]),"difficulty":int(r.get("difficulty",3) or 3),"score":float(r["score"]),"max_score":float(r["max_score"]),"error_type":str(r.get("error_type","其他")),"skill":str(r.get("skill","基础知识")),"note":str(r.get("note",""))})
                persist(); st.success(f"导入 {len(df)} 条题目数据"); st.rerun()
        except Exception as e: st.error(str(e))

with tabs[9]:
    st.subheader("⚙️ 系统设置与连接状态")
    a,b = st.columns(2)
    with a:
        st.markdown("#### ☁️ 云数据库")
        if CLOUD_MODE: st.success("Supabase 已配置，教师登录与云端持久化已启用。")
        else:
            st.warning("尚未配置 Supabase，目前为原型本地存储。")
            st.code('SUPABASE_URL = "https://xxxx.supabase.co"\nSUPABASE_PUBLISHABLE_KEY = "sb_publishable_xxx"\nALLOWED_TEACHER_EMAIL = "你的邮箱"')
            st.caption("先在 Supabase SQL Editor 执行项目内 supabase_setup.sql，再把以上值放进 Streamlit Secrets。")
    with b:
        st.markdown("#### 🧠 中国大陆AI · 阿里云百炼")
        if AI_READY:
            st.success(f"百炼AI已配置：{QWEN_MODEL}")
            st.caption(f"Base URL：{DASHSCOPE_BASE_URL}")
        else:
            st.warning("尚未配置百炼 API，目前使用规则版报告。")
            st.code(
                'DASHSCOPE_API_KEY = "你的百炼API Key"\n'
                'QWEN_MODEL = "qwen3.8-flash"\n'
                'DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"'
            )
            st.caption("API Key 只放 Streamlit Secrets，不要上传 GitHub。默认使用华北2（北京）OpenAI兼容地址。")
    st.markdown("#### 当前数据边界")
    st.write("V1.1.1 默认不把学生姓名和学校发送给AI；家长报告和AI诊断均需教师审核；AI只接收当前学生的教学数据摘要。")
