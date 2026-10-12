# 减肥数据看板 MVP

> 你的减肥私人数据分析师 —— 45天挑战的配套产品。

## 快速开始

```bash
cd weight-loss-mvp
pip install -r requirements.txt
streamlit run app.py
```

浏览器会自动打开 `http://localhost:8501`。

## 功能（MVP 范围）

- 📝 数据录入：体重、热量、睡眠、心情（1-5）、备注
- 📊 数据看板：体重趋势（含7日均线）、热量、睡眠、心情图表 + 异常波动检测
- 🤖 AI 周报：有 API Key 用 DeepSeek/OpenAI 生成专业周报，无 Key 自动回退到本地规则报告
- 🔒 付费墙：Gumroad License 验证（演示开关，默认关闭）

## 配置 AI 引擎（可选）

在网页左侧侧边栏填入 API Key，或设置环境变量：

```bash
# Windows PowerShell
$env:DEEPSEEK_API_KEY="sk-xxxx"

# 或 OpenAI
$env:OPENAI_API_KEY="sk-xxxx"
```

- **DeepSeek**（推荐，便宜中文强）：https://platform.deepseek.com
- **OpenAI**：https://platform.openai.com

## 目录结构

```
weight-loss-mvp/
├── app.py          # 主程序（Streamlit 界面）
├── db.py           # 数据库（SQLite，可换 Supabase）
├── charts.py       # Plotly 图表 + 异常检测
├── ai_report.py    # AI 周报（LLM + 规则回退）
├── license.py      # Gumroad 付费墙
├── requirements.txt
└── data/           # 本地数据（自动生成，勿提交到 git）
```
