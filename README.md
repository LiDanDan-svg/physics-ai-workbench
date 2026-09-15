# 旦旦物理 · AI教学工作台 V1.2

面向独立物理老师的云端学情与AI教学工作台。

## V1.2 新增

### 1. AI试卷识别
- 支持 PDF、PNG、JPG、JPEG、WebP
- PDF 单次最多1份；图片单次最多8张
- 千问自动拆题并建议：题号、题意摘要、知识点、能力维度、难度、分值、题型、参考答案、易错点
- 如果批改痕迹清晰，AI可尝试识别学生得分；不清晰时保持为空
- 识别结果必须经过教师在可编辑表格中校对
- 校对后可一键导入某名学生的一次考试
- 原始PDF/图片不写入 Supabase，只保存教师确认后的结构化结果
- 可保存“试卷模板”和下载解析 CSV

### 2. 个性化练习
- 根据学生长期学情、薄弱知识点和近期错误类型生成原创训练
- 支持2~12题
- 难度：由易到难 / 中档为主 / 冲刺综合 / 基础巩固
- 风格：高考常见模型 / 校内月考 / 专题小测 / 概念+计算 / 综合迁移
- 自动输出答案、解析、易错点、验收标准
- 支持学生版（无答案）和教师版（含解析）下载
- 可保存到云端工作区

### 3. 隐私与数据保护
- 学情诊断仍默认不发送学生显示名称和学校
- AI试卷识别会发送你主动上传的 PDF/图片内容，因此上传前必须去除或遮挡学生姓名、准考证号等不必要身份信息
- 原始试卷文件不写入 Supabase
- AI生成的题目、答案、试卷解析结果必须由教师审核

## 现有功能
- Supabase 教师邮箱登录
- 云端学生档案与多设备同步
- 考试与题目级数据
- 知识点掌握度、失分原因、六维能力雷达
- 纵向学情变化
- 百炼千问教师诊断
- 家长版报告
- 本周教学任务
- 30天方案
- JSON备份/恢复
- CSV批量导入

## Streamlit Secrets

```toml
SUPABASE_URL = "https://YOUR_PROJECT.supabase.co"
SUPABASE_PUBLISHABLE_KEY = "sb_publishable_xxx"
ALLOWED_TEACHER_EMAIL = "teacher@example.com"

DASHSCOPE_API_KEY = "sk-xxx"
QWEN_MODEL = "qwen3.8-flash"
QWEN_VISION_MODEL = "qwen3.8-flash"
QWEN_PRACTICE_MODEL = "qwen3.8-flash"
DASHSCOPE_BASE_URL = "https://YOUR_WORKSPACE.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
```

如果已经配置 V1.1.1，只新增 `QWEN_VISION_MODEL` 和 `QWEN_PRACTICE_MODEL` 即可；不新增也能运行，程序默认使用 `qwen3.8-flash`。

## 升级方式

从 V1.1.1.1 升级只需覆盖/新增：

- `app.py`
- `storage.py`
- `paper_ai.py`（新增）
- `practice_ai.py`（新增）
- `README.md`
- `.streamlit/secrets.example.toml`（仅示例，不影响已有 Streamlit Secrets）

不需要重新执行 Supabase SQL，不需要删除原云端数据。

## 重要提醒

AI 对试卷、批改分数、参考答案的识别可能出错；AI生成物理题也可能出现条件遗漏、数值不自洽或多解。**所有结果必须由物理老师审核后进入正式教学流程。**
