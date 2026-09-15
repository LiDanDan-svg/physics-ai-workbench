# 旦旦物理 · AI教学工作台 V1.1.1（中国大陆AI版）

面向独立物理老师的轻量教学工作台。

## V1.1.1 新增

- AI底层从 OpenAI API 切换为 **阿里云百炼 / 通义千问**
- 默认模型：`qwen3.8-flash`
- 默认中国大陆接入地址：`https://dashscope.aliyuncs.com/compatible-mode/v1`
- 支持百炼 OpenAI 兼容 Responses API，并自动回退 Chat Completions
- 教师版诊断、家长报告、本周教学任务、30天方案全部支持千问生成
- 新增 **AI数据隐私预览**：调用前可查看本次发送给AI的教学摘要
- 默认不把学生姓名、学校发送给AI
- AI失败时仍可继续使用规则诊断
- 保留 Supabase 教师登录、云数据库、多设备同步

## Streamlit Secrets

```toml
SUPABASE_URL = "https://YOUR_PROJECT.supabase.co"
SUPABASE_PUBLISHABLE_KEY = "sb_publishable_xxx"
ALLOWED_TEACHER_EMAIL = "teacher@example.com"

DASHSCOPE_API_KEY = "sk-..."
QWEN_MODEL = "qwen3.8-flash"
DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
```

> 百炼 API Key 只放 Streamlit Secrets，不要提交到 GitHub。

## 百炼配置建议

1. 在阿里云百炼开通模型服务。
2. 优先使用华北2（北京）地域。
3. 创建 API Key。
4. 将 Key 填入 `DASHSCOPE_API_KEY`。
5. 第一阶段使用 `qwen3.8-flash` 做学情诊断和家长报告即可。
6. 如使用业务空间专属域名，可把 `DASHSCOPE_BASE_URL` 换成对应空间的 OpenAI 兼容 Base URL。

## 隐私边界

- 建议学生使用编号/化名。
- 不录入身份证号、家庭住址等与教学无关的数据。
- 默认不向AI发送学生显示名称和学校。
- 教师备注会作为教学上下文发送给AI，请不要在备注中填写无关敏感信息。
- 所有家长报告、AI诊断在对外发送前都应由教师人工审核。
