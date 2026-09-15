# 旦旦物理 · AI教学工作台 V1.0

面向独立物理老师的轻量教学工作台。

## V1.0 功能
- 学生档案
- 考试记录
- 题目级得分/知识点/错误原因
- 成绩趋势
- 知识点掌握度
- 失分原因分布
- 六维能力雷达
- 智能学情诊断报告（可解释规则引擎）
- 30天提升方案
- 学生CSV/题目CSV批量导入
- JSON完整备份与恢复

## 本地运行
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Streamlit Cloud 部署
1. 新建 GitHub 仓库，例如 `physics-ai-workbench`
2. 上传本项目全部文件到仓库根目录
3. Streamlit Community Cloud 创建 App
4. Main file path 选择 `app.py`
5. Deploy

## 数据说明
V1.0 默认使用本地 JSON 文件保存数据。在 Streamlit Cloud 上，容器重启/重新部署可能导致本地数据丢失，因此请定期使用左侧“下载工作区备份(JSON)”。

下一版建议接 Supabase/Postgres，实现真正的云端长期持久化与多设备同步。

## 隐私建议
- 优先使用学生编号、化名
- 不采集身份证、家庭住址等无关敏感信息
- 公开演示视频请使用演示数据
- 向第三方AI模型发送数据前，应先做脱敏并取得适当授权
