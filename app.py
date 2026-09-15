from __future__ import annotations
import uuid
from datetime import date, datetime
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
import ai_engine as _ai_engine
from paper_ai import parse_paper_files, DEFAULT_VISION_MODEL
from practice_ai import generate_practice_set, practice_markdown, DEFAULT_PRACTICE_MODEL

ai_configured = _ai_engine.ai_configured
generate_ai_report = _ai_engine.generate_ai_report
DEFAULT_DASHSCOPE_BASE_URL = getattr(_ai_engine, "DEFAULT_DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
DEFAULT_QWEN_MODEL = getattr(_ai_engine, "DEFAULT_QWEN_MODEL", "qwen3.8-flash")
AI_ENGINE_VERSION = getattr(_ai_engine, "ENGINE_VERSION", "legacy-compatible")

def ai_payload_preview(data, student):
    fn = getattr(_ai_engine, "ai_payload_preview", None)
    if callable(fn):
        return fn(data, student)
    # 兼容旧引擎：只生成最小化预览，避免因文件版本不同导致整个应用崩溃。
    snap = student_snapshot(data, student["student_id"])
    return {
        "student": {
            "student_id": student.get("student_id"),
            "grade": student.get("grade"),
            "target_score": student.get("target_score"),
            "teacher_notes": student.get("notes", ""),
        },
        "learning_snapshot": snap,
        "engine_status": "legacy-compatible; please update ai_engine.py",
    }

st.set_page_config(page_title="旦旦物理 · AI教学工作台", page_icon="🧠", layout="wide")
APP_VERSION = "1.2.0"

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
QWEN_VISION_MODEL = str(secret("QWEN_VISION_MODEL", DEFAULT_VISION_MODEL)).strip() or DEFAULT_VISION_MODEL
QWEN_PRACTICE_MODEL = str(secret("QWEN_PRACTICE_MODEL", DEFAULT_PRACTICE_MODEL)).strip() or DEFAULT_PRACTICE_MODEL
DASHSCOPE_BASE_URL = str(secret("DASHSCOPE_BASE_URL", DEFAULT_DASHSCOPE_BASE_URL)).strip() or DEFAULT_DASHSCOPE_BASE_URL
CLOUD_MODE = bool(SUPABASE_URL and SUPABASE_KEY)
AI_READY = ai_configured(DASHSCOPE_API_KEY)
AI_PROVIDER_LABEL = f"阿里云百炼 · {QWEN_MODEL}"


def cloud_login_gate():
    from cloud_store import create_supabase_client, sign_in, sign_up, load_cloud_workspace
    if st.session_state.get("sb_client") and st.session_state.get("teacher_user"):
        return
    st.title("🧠 旦旦物理 · AI教学工作台")
    st.caption(f"V{APP_VERSION}｜云端学情 · 百炼千问AI · 试卷AI识别 · 个性化练习")
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
st.caption(f"V{APP_VERSION}｜云端学情 · 试卷/PDF AI识别 · 自动知识点标注 · 个性化练习")
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

tabs = st.tabs(["🏠 总览", "👤 学生管理", "📝 考试与题目", "📊 学情分析", "🧠 AI诊断", "👨‍👩‍👧 家长报告", "📌 本周教学", "📅 30天方案", "📄 AI试卷识别", "🧩 个性化练习", "📥 批量导入", "⚙️ 系统设置"])

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
    st.subheader("📄 AI试卷识别 · 自动知识点标注")
    st.caption("上传PDF或试卷照片 → 千问读取题目 → 自动标知识点/能力/难度/分值 → 老师校对 → 导入学生考试。原始文件不会写入Supabase，只有你确认后的结构化结果才会保存。")
    st.warning("隐私提醒：如果试卷/答题卡上含学生真实姓名、准考证号、学校等，请先遮挡或裁剪。此模块会把你上传的文件内容发送给阿里云百炼模型处理。")

    if not AI_READY:
        st.info("请先配置阿里云百炼 API。未配置时仍可继续使用原有手工录题功能。")
    else:
        uploaded = st.file_uploader(
            "上传试卷PDF或图片（PDF最多1份；图片最多8张）",
            type=["pdf", "png", "jpg", "jpeg", "webp"],
            accept_multiple_files=True,
            key="paper_files_v12",
        )
        extra_inst = st.text_input("补充说明（可选）", placeholder="例如：这是高一牛顿运动定律单元测；总分100分")
        privacy_ok = st.checkbox("我已确认文件中无不必要的学生身份信息，或已完成遮挡/裁剪", key="paper_privacy_ok")
        if uploaded:
            total_mb = sum(getattr(f, "size", 0) for f in uploaded) / 1024 / 1024
            st.caption(f"已选择 {len(uploaded)} 个文件，合计约 {total_mb:.1f} MB。为了云端稳定，建议单次总量不超过40MB。")
        if st.button("🧠 AI解析试卷", type="primary", disabled=not(bool(uploaded) and privacy_ok), use_container_width=True):
            try:
                if sum(getattr(f, "size", 0) for f in uploaded) > 40 * 1024 * 1024:
                    raise ValueError("单次上传总量超过40MB，请拆分后解析。")
                payload=[]
                for f in uploaded:
                    payload.append({"name": f.name, "mime": f.type, "bytes": f.getvalue()})
                with st.spinner("千问正在读取试卷并拆分题目，PDF可能需要几十秒……"):
                    parsed = parse_paper_files(
                        payload, DASHSCOPE_API_KEY, DASHSCOPE_BASE_URL,
                        QWEN_VISION_MODEL, extra_inst,
                    )
                st.session_state.paper_parse_draft_v12 = parsed
                st.success(f"解析完成：识别到 {len(parsed.get('questions', []))} 道题。请先人工校对再保存。")
            except Exception as e:
                st.error(f"试卷解析失败：{e}")

        parsed = st.session_state.get("paper_parse_draft_v12")
        if parsed:
            a,b,c,d = st.columns(4)
            a.metric("试卷", parsed.get("paper_title") or "未命名")
            b.metric("题数", len(parsed.get("questions", [])))
            c.metric("识别总分", f"{float(parsed.get('total_score',0) or 0):.1f}")
            d.metric("视觉模型", parsed.get("model", QWEN_VISION_MODEL))
            if parsed.get("warnings"):
                st.warning("；".join(map(str, parsed.get("warnings", []))))

            rows = parsed.get("questions", [])
            df = pd.DataFrame(rows)
            required_cols = ["question_no","stem_summary","topic","skill","difficulty","max_score","student_score","question_type","error_type","note","reference_answer","common_trap"]
            for col in required_cols:
                if col not in df.columns:
                    df[col] = None
            edited = st.data_editor(
                df[required_cols],
                use_container_width=True,
                hide_index=True,
                num_rows="dynamic",
                column_config={
                    "skill": st.column_config.SelectboxColumn("能力维度", options=SKILLS),
                    "error_type": st.column_config.SelectboxColumn("主要错误原因", options=ERROR_TYPES),
                    "difficulty": st.column_config.NumberColumn("难度", min_value=1, max_value=5, step=1),
                    "student_score": st.column_config.NumberColumn("学生得分（可空）", min_value=0.0, step=0.5),
                    "max_score": st.column_config.NumberColumn("满分", min_value=0.0, step=0.5),
                },
                key="paper_editor_v12",
            )
            st.caption("题意摘要、参考答案和AI识别得分都可能有误；保存前请老师人工核对。")

            csv_bytes = edited.to_csv(index=False).encode("utf-8-sig")
            st.download_button("⬇️ 下载解析结果CSV", csv_bytes, file_name="paper_ai_parsed.csv", mime="text/csv")

            x,y = st.columns(2)
            with x:
                if st.button("💾 保存为试卷模板", use_container_width=True):
                    template = {
                        "template_id": "T" + uuid.uuid4().hex[:8].upper(),
                        "paper_title": parsed.get("paper_title") or "AI解析试卷",
                        "grade": parsed.get("grade", ""),
                        "source_files": parsed.get("source_files", []),
                        "created_at": datetime.now().isoformat(timespec="seconds"),
                        "questions": edited.where(pd.notna(edited), None).to_dict("records"),
                    }
                    data.setdefault("paper_templates", []).append(template)
                    persist(); st.success("试卷模板已保存到云端工作区。")
            with y:
                if data.get("paper_templates"):
                    st.caption(f"当前已保存 {len(data['paper_templates'])} 份试卷模板")

            st.markdown("#### 导入为某位学生的一次考试")
            if not students:
                st.info("请先在“学生管理”添加学生。")
            else:
                a,b,c = st.columns(3)
                import_sid = a.selectbox("学生", [x["student_id"] for x in students], key="paper_import_student", format_func=lambda z: student_label(find_student(z)))
                import_name = b.text_input("考试名称", value=parsed.get("paper_title") or "AI解析考试", key="paper_import_name")
                import_date = c.date_input("考试日期", value=date.today(), key="paper_import_date")
                score_missing = int(edited["student_score"].isna().sum()) if "student_score" in edited.columns else len(edited)
                allow_blank_zero = False
                if score_missing:
                    st.warning(f"当前有 {score_missing} 道题没有学生得分。为避免污染学情数据，默认禁止导入。请补全得分，或明确允许空分按0分处理。")
                    allow_blank_zero = st.checkbox("我确认：仍然把未填写得分的题按0分导入", key="paper_allow_blank_zero")
                if st.button("✅ 校对完成，导入学生考试", type="primary", use_container_width=True, disabled=bool(score_missing and not allow_blank_zero)):
                    try:
                        rows2 = edited.where(pd.notna(edited), None).to_dict("records")
                        if not rows2:
                            raise ValueError("没有可导入题目")
                        eid = "E" + uuid.uuid4().hex[:8].upper()
                        max_total = sum(float(r.get("max_score") or 0) for r in rows2)
                        actual_total = sum(float(r.get("student_score") or 0) for r in rows2)
                        data["exams"].append({
                            "exam_id": eid, "student_id": import_sid,
                            "exam_name": import_name or "AI解析考试", "date": str(import_date),
                            "total_score": actual_total, "max_score": max_total or 100.0,
                            "source": "ai_paper_v12",
                        })
                        for i,r in enumerate(rows2, start=1):
                            max_sc=float(r.get("max_score") or 0)
                            score=float(r.get("student_score") or 0)
                            data["questions"].append({
                                "exam_id":eid,"student_id":import_sid,
                                "question_no":int(r.get("question_no") or i),
                                "topic":str(r.get("topic") or "未分类"),
                                "difficulty":int(r.get("difficulty") or 3),
                                "score":score,"max_score":max_sc,
                                "error_type":str(r.get("error_type") or ("无" if max_sc and score>=max_sc else "其他")),
                                "skill":str(r.get("skill") or "模型识别"),
                                "note":str(r.get("note") or ""),
                                "stem_summary":str(r.get("stem_summary") or ""),
                                "reference_answer":str(r.get("reference_answer") or ""),
                                "common_trap":str(r.get("common_trap") or ""),
                                "question_type":str(r.get("question_type") or ""),
                                "source":"ai_paper_v12",
                            })
                        persist(); st.success(f"已导入考试 {eid}：{len(rows2)} 道题，总得分 {actual_total:g}/{max_total:g}")
                    except Exception as e:
                        st.error(f"导入失败：{e}")

with tabs[9]:
    st.subheader("🧩 个性化练习 · 按薄弱点自动生成")
    st.caption("根据学生长期学情生成原创训练题，不复制上传试卷原题。AI生成题目与答案必须由老师审核后再布置。")
    if not students:
        st.warning("请先新增学生。")
    elif not AI_READY:
        st.warning("请先配置阿里云百炼 API。")
    else:
        sid = st.selectbox("选择学生", [x["student_id"] for x in students], key="practice_student", format_func=lambda z: student_label(find_student(z)))
        student = find_student(sid)
        snap = student_snapshot(data, sid)
        all_topics = [str(x.get("知识点")) for x in snap.get("topic_mastery", []) if x.get("知识点")]
        defaults = [str(x.get("知识点")) for x in snap.get("weaknesses", [])[:2] if x.get("知识点")]
        selected_topics = st.multiselect("本次训练知识点", all_topics, default=[x for x in defaults if x in all_topics], help="留空时由AI根据当前薄弱项自动选择")
        a,b,c = st.columns(3)
        count = a.slider("题目数量", 2, 12, 5)
        diff_mode = b.selectbox("难度结构", ["由易到难", "以中档题为主", "冲刺综合题", "基础巩固"])
        style = c.selectbox("训练风格", ["高考常见模型", "校内月考风格", "专题小测", "概念辨析+计算", "综合迁移"])
        if st.button("✨ 生成个性化练习", type="primary", use_container_width=True):
            try:
                with st.spinner("千问正在根据学情设计原创练习……"):
                    pset = generate_practice_set(
                        data, student, DASHSCOPE_API_KEY, DASHSCOPE_BASE_URL,
                        QWEN_PRACTICE_MODEL, count, selected_topics, diff_mode, style,
                    )
                st.session_state.practice_draft_v12 = pset
                st.success("练习已生成。请先逐题审核答案、条件和数值。")
            except Exception as e:
                st.error(f"练习生成失败：{e}")

        pset = st.session_state.get("practice_draft_v12")
        if pset and pset.get("student_id") == sid:
            st.markdown(f"### {pset.get('title','个性化训练')}")
            st.write(pset.get("training_goal", ""))
            st.warning("AI生成物理题可能存在条件遗漏、数值错误或多解。老师审核通过后再发送给学生。")
            for q in pset.get("questions", []):
                with st.expander(f"第{q.get('no')}题｜{q.get('topic')}｜难度{q.get('difficulty')}", expanded=True):
                    st.markdown(q.get("question", ""))
                    st.markdown(f"**答案：** {q.get('answer','')}")
                    st.markdown(f"**解析：** {q.get('solution','')}")
                    st.caption(f"易错点：{q.get('common_trap','')}｜验收：{q.get('acceptance','')}")
            teacher_md = practice_markdown(pset, True)
            student_md = practice_markdown(pset, False)
            a,b,c = st.columns(3)
            a.download_button("⬇️ 学生版（无答案）", student_md.encode("utf-8"), file_name=f"{sid}_practice_student.md", mime="text/markdown", use_container_width=True)
            b.download_button("⬇️ 教师版（含解析）", teacher_md.encode("utf-8"), file_name=f"{sid}_practice_teacher.md", mime="text/markdown", use_container_width=True)
            if c.button("💾 保存本次练习", use_container_width=True):
                pid=pset.get("practice_id")
                if not any(x.get("practice_id")==pid for x in data.setdefault("practice_sets", [])):
                    saved=dict(pset); saved["created_at"]=datetime.now().isoformat(timespec="seconds")
                    data["practice_sets"].append(saved); persist(); st.success("练习已保存到云端工作区。")
                else:
                    st.info("这份练习已经保存过。")

        saved_sets=[x for x in data.get("practice_sets",[]) if x.get("student_id")==sid]
        if saved_sets:
            st.markdown("#### 已保存练习")
            st.dataframe(pd.DataFrame([{"练习ID":x.get("practice_id"),"标题":x.get("title"),"题数":len(x.get("questions",[])),"生成时间":x.get("created_at","")} for x in saved_sets]), use_container_width=True, hide_index=True)

with tabs[10]:
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

with tabs[11]:
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
            st.caption(f"诊断模型：{QWEN_MODEL}｜试卷视觉：{QWEN_VISION_MODEL}｜练习生成：{QWEN_PRACTICE_MODEL}")
            st.caption(f"Base URL：{DASHSCOPE_BASE_URL}")
            st.caption(f"AI引擎：{AI_ENGINE_VERSION}")
        else:
            st.warning("尚未配置百炼 API，目前使用规则版报告。")
            st.code(
                'DASHSCOPE_API_KEY = "你的百炼API Key"\n'
                'QWEN_MODEL = "qwen3.8-flash"\n'
                'QWEN_VISION_MODEL = "qwen3.8-flash"\n'
                'QWEN_PRACTICE_MODEL = "qwen3.8-flash"\n'
                'DASHSCOPE_BASE_URL = "你的百炼OpenAI兼容地址"'
            )
            st.caption("API Key 只放 Streamlit Secrets，不要上传 GitHub。优先使用百炼控制台显示的业务空间专属 OpenAI 兼容地址。")
    st.markdown("#### 当前数据边界")
    st.write("V1.2 的学情诊断默认不把学生姓名和学校发送给AI；但“AI试卷识别”会发送你主动上传的PDF/图片文件内容，因此请先去除学生姓名、准考证号等不必要信息。AI生成练习和答案必须由教师审核。")
