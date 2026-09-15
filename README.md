# 旦旦物理 · AI教学工作台 V1.1

面向独立物理老师的轻量教学工作台。

## V1.1新增
- Supabase 教师邮箱/密码登录
- 云端工作区持久化，多设备同步
- Row Level Security：每个教师只读取自己的工作区
- 多次考试纵向知识点变化
- 真AI教师诊断（可选 OpenAI API）
- 家长版学情报告
- 本周教学任务
- 30天提升方案升级
- 数据置信度与“可改善失分量”表述，避免把估算写成提分承诺

## 直接部署
即使不配置 Supabase / AI，V1.1 也能以“本地原型 + 规则诊断”方式运行。

```bash
pip install -r requirements.txt
streamlit run app.py
```

## 正式云端数据配置
1. 创建 Supabase 项目。
2. 在 SQL Editor 执行 `supabase_setup.sql`。
3. 在 Authentication 中创建/注册教师账号（可保留邮箱确认）。
4. 在 Streamlit App -> Settings -> Secrets 中配置：

```toml
SUPABASE_URL = "https://YOUR_PROJECT.supabase.co"
SUPABASE_PUBLISHABLE_KEY = "sb_publishable_xxx"
ALLOWED_TEACHER_EMAIL = "your@email.com"
```

Supabase Python 客户端使用邮箱+密码登录，数据库表启用 RLS，数据按 `auth.uid()` 隔离。

## 真AI配置
在 Streamlit Secrets 增加：

```toml
OPENAI_API_KEY = "你的API Key"
OPENAI_MODEL = "gpt-5.6-luna"
```

不配置 API Key 时，系统自动回退到可解释规则版，不影响其他功能。

## 隐私原则
- 推荐学生编号/化名；
- 不采集身份证号、家庭住址等无关敏感信息；
- AI报告仅发送当前学生的教学摘要，并要求教师审核；
- API Key 与数据库 Key 只放 Streamlit Secrets，不提交 GitHub。
