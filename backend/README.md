# Deep Research Agent

基于 LangGraph 的多智能体深度研究系统。

## 架构

```
用户输入 → Planner(任务拆解) → Executor(搜索+摘要) → Reporter(报告生成) → Critic(评分反馈)
                ↑                                                                    |
                └────────────────── 迭代优化 ←──────────────────────────────────────┘
```

## 启动

```bash
# 后端
cd backend
.venv/Scripts/python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# 前端
cd frontend
npx vite --port 5174
```

## 配置

复制 `.env` 并修改 API Key：
- `LLM_API_KEY` — DashScope API Key
- `TAVILY_API_KEY` — Tavily 搜索 API Key
- `CRITIC_SCORE_THRESHOLD` — Critic 评分阈值（默认 4.0）
- `MAX_RESEARCH_ITERATIONS` — 最大迭代次数（默认 2）
