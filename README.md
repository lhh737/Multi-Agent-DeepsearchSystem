# Multi-Agent Deep Research System

<div align="center">

**基于 LangGraph 的多智能体深度研究系统 · 输入主题，自动产出结构化研究报告**

[![Python](https://img.shields.io/badge/Python-3.12-blue)](https://www.python.org/)
[![LangGraph](https://img.shields.io/badge/LangGraph-1.1+-orange)](https://github.com/langchain-ai/langgraph)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.136+-009688)](https://fastapi.tiangolo.com/)
[![Vue](https://img.shields.io/badge/Vue-3.5-green)](https://vuejs.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow)](./LICENSE)

</div>

---

## 项目简介

输入一个研究主题，系统自动完成「**任务拆解 → 多源搜索 → 分析总结 → 报告生成 → 质量评审 → 迭代优化**」全流程。围绕 LangGraph 构建了 Planner / Executor / Reporter / Critic 四个专用 Agent，通过条件路由（Conditional Edges）实现评分不足时自动触发补充检索与报告优化，最终输出一份结构严谨、来源可追溯的 Markdown 研究报告。

## 效果展示

<div align="center">

**图1. 首页效果图**

<img src="demo/demo1_首页效果图.png" alt="首页效果图" width="90%">

&nbsp;

**图2. 子任务进程效果图**

<img src="demo/demo3_子任务进程.png" alt="子任务进程效果图" width="90%">

&nbsp;

**图3. 研究报告效果图**

<img src="demo/demo2_研究报告.png" alt="研究报告效果图" width="90%">

</div>

## 技术架构

```
                            用户输入研究主题
                                  │
                                  ▼
    ┌─────────────────────────────────────────────────────────────┐
    │                    LangGraph 状态机                          │
    │                                                             │
    │  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌────────┐│
    │  │ Planner  │───→│ Executor │───→│ Reporter │───→│ Critic ││
    │  │ 任务拆解  │    │ 搜索+摘要 │    │ 报告生成  │    │ 质量评分 ││
    │  │ 3~5子任务 │    │ 多源检索  │    │ 六章结构  │    │ 五维评估 ││
    │  └──────────┘    └──────────┘    └──────────┘    └───┬────┘│
    │       ↑                                              │      │
    │       │         评分 < 阈值 → 携带反馈重搜              │      │
    │       └──────────────────────────────────────────────┘      │
    └─────────────────────────────────────────────────────────────┘
           │                    │                    │
           ▼                    ▼                    ▼
    ┌────────────┐    ┌──────────────┐    ┌────────────────┐
    │   Tavily   │    │ PostgreSQL 16│    │    Redis 7      │
    │  混合搜索   │    │  会话·任务   │    │  MD5 语义缓存    │
    │  +DDG 兜底 │    │  全量持久化   │    │  TTL 3600s      │
    └────────────┘    └──────────────┘    └────────────────┘
```

### Agent 职责

| 阶段 | Agent | 核心职责 |
|:---:|---|---|
| **1** | **Planner** | 接收研究主题，LLM 拆解为 3~5 个互补子任务，为每个子任务生成英文检索关键词 |
| **2** | **Executor** | 逐任务执行：Tavily / DuckDuckGo 搜索 → 查 Redis 缓存 → LLM 深度分析摘要（四维度展开 + 来源编号） |
| **3** | **Reporter** | 整合所有子任务摘要，按「执行摘要 → 核心发现 → 详细分析 → 对比洞察 → 风险建议 → 总结展望」六章模板输出报告 |
| **4** | **Critic** | 从完整性、准确性、结构、深度、可操作性五个维度对报告评分（1~5），低于阈值时生成改进建议并触发下一轮迭代 |

### 迭代优化机制

```
第 1 轮: Planner → Executor → Reporter → Critic (3.5/5, 不合格)
                                                    │
                                    携带反馈 ↓      第 2 轮: Executor(补充搜索) → Reporter(优化报告) → Critic (4.2/5, 通过 → END)
```

## 核心特性

### Multi-Agent 协作
基于 **LangGraph StateGraph** 构建，4 个 Agent 通过 Shared State 传递上下文，conditional edges 实现动态路由。初始规划后并行执行搜索与摘要，由 Reporter 统一整合，Critic 最终把关。

### LLM-as-Judge 质量评审
Critic Agent 从 5 个维度对报告客观评分，输出 JSON 结构化反馈（优点 / 缺陷 / 建议检索方向）。评分未达阈值时自动携带反馈回到 Executor 执行补充检索，最多 2 轮迭代优化。

### 混合搜索 + 语义缓存
- **主搜索**: Tavily Search API（advanced 模式，AI 摘要）
- **兜底搜索**: DuckDuckGo（免费、无需 API Key）
- **Redis 缓存**: 对每条搜索 query 生成 MD5 摘要作为 key，缓存结果 TTL 1 小时，避免相同主题重复调用 LLM

### 状态持久化
- **PostgreSQL 16**: `research_sessions` + `research_tasks` 两张表，完整记录每次研究的输入、过程、输出、评分
- **历史回溯**: 支持查询历史会话列表、查看任意会话的详细过程与最终报告
- **容错降级**: 数据库/Redis 不可用时自动切换内存存储，系统不中断

### SSE 实时流式推送
FastAPI Server-Sent Events 将研究进度实时推送到前端：任务规划 → 各任务执行状态 → Critic 评分 → 最终报告，前端即时渲染，无白屏等待。

### LangSmith 全链路追踪（可选）
代码已集成 LangSmith SDK，填入 `LANGSMITH_API_KEY` 即可在 LangSmith 控制台查看每次 Agent 调用的输入/输出/耗时/Token 消耗，便于调试与性能分析。

## 技术栈

| 层级 | 技术选型 | 说明 |
|---|---|---|
| **AI 编排** | LangGraph 1.1 | StateGraph + Conditional Edges |
| **LLM** | Qwen / GPT / 任意 OpenAI 兼容 API | 默认 DashScope，可切换 |
| **后端** | FastAPI + uvicorn | SSE 流式 + asyncio |
| **数据库** | PostgreSQL 16 (asyncpg) | 会话任务持久化 |
| **缓存** | Redis 7 (redis-py) | 搜索语义缓存 MD5 + TTL |
| **追踪** | LangSmith | 可选，填入 Key 即启用 |
| **前端** | Vue 3 + TypeScript | Composition API |
| **Markdown** | marked | 表格 / 代码块 / 公式 |
| **搜索** | Tavily + DuckDuckGo | 混合多源 |
| **部署** | Docker Compose | PG + Redis 一键启动 |

## 快速开始

### 环境要求

- **Python** ≥ 3.10
- **Node.js** ≥ 18
- **Docker Desktop**（运行 PostgreSQL 和 Redis）

### 1. 克隆仓库

```bash
git clone git@github.com:lhh737/Multi-Agent-DeepsearchSystem.git
cd Multi-Agent-DeepsearchSystem
```

### 2. 启动数据库和缓存

```bash
docker compose up -d
```

### 3. 配置 LLM 和搜索 API Key

编辑 `backend/.env`：

```env
# ===== LLM（必填）=====
# 支持所有 OpenAI 兼容接口：DashScope / OpenAI / DeepSeek / 本地模型
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_API_KEY=sk-your-api-key
LLM_MODEL_ID=qwen3.6-flash
LLM_TIMEOUT=300

# ===== 搜索（推荐填 Tavily，不填则用 DuckDuckGo）=====
SEARCH_API=tavily
TAVILY_API_KEY=tvly-your-tavily-key

# ===== LangSmith（可选，用于全链路追踪调试）=====
LANGSMITH_API_KEY=lsv2-your-langsmith-key

# ===== 数据库（Docker Compose 默认，一般无需修改）=====
PG_HOST=localhost
PG_PORT=5432
PG_USER=deepresearch
PG_PASSWORD=deepresearch
PG_DATABASE=deepresearch

# ===== Redis（Docker Compose 默认）=====
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_CACHE_TTL=3600

# ===== 研究参数 =====
MAX_RESEARCH_ITERATIONS=2
CRITIC_SCORE_THRESHOLD=4.0
```

### 4. 安装依赖并启动

```bash
# ── 后端 ──
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt   # Windows
# source .venv/bin/pip install -r requirements.txt  # macOS / Linux
.venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# ── 前端（新终端）──
cd frontend
npm install
npx vite --port 5174
```

### 5. 打开浏览器

访问 **http://localhost:5174**，输入研究主题即可开始。

## 项目结构

```
Multi-Agent-DeepsearchSystem/
│
├── backend/                          # 后端服务
│   ├── app/
│   │   ├── main.py                   # FastAPI 入口 · SSE 流式 · 生命周期
│   │   ├── config.py                 # 环境变量管理
│   │   ├── agents/                   # ▸ 4 个 Agent 节点
│   │   │   ├── planner.py            #   任务规划 Agent（LLM 拆解主题）
│   │   │   ├── executor.py           #   搜索执行 Agent（搜索 + 摘要）
│   │   │   ├── reporter.py           #   报告生成 Agent（六章模板）
│   │   │   └── critic.py             #   质量评审 Agent（五维 LLM-as-Judge）
│   │   ├── graph/                    # ▸ LangGraph 状态机
│   │   │   ├── state.py              #   TypedDict 状态定义
│   │   │   └── builder.py            #   图构建 · 条件路由 · 持久化集成
│   │   ├── tools/search.py           # ▸ 搜索工具（Tavily + DDG + Redis 缓存）
│   │   ├── prompts/templates.py      # ▸ 提示词模板（中文优化）
│   │   ├── persistence/              # ▸ PostgreSQL 持久层
│   │   │   ├── database.py           #   连接池 · schema 初始化 · 降级
│   │   │   └── repository.py         #   会话/任务 CRUD
│   │   ├── cache/redis_cache.py      # ▸ Redis 缓存（MD5 + TTL · 内存降级）
│   │   └── tracing/langsmith.py      # ▸ LangSmith 追踪（可选）
│   ├── requirements.txt
│   ├── pyproject.toml
│   └── .env                          # 环境变量（不纳入版本控制）
│
├── frontend/                         # 前端界面
│   ├── src/
│   │   ├── App.vue                   # 主组件（暗色模式 · 迭代可视化 · 复制下载）
│   │   ├── services/api.ts           # SSE 流式客户端
│   │   ├── style.css                 # 全局样式
│   │   └── main.ts                   # Vue 入口
│   ├── index.html
│   ├── package.json
│   └── vite.config.ts
│
├── demo/                             # 效果截图
│   ├── demo1_首页效果图.png
│   ├── demo2_研究报告.png
│   └── demo3_子任务进程.png
│
├── docker-compose.yml                # PostgreSQL 16 + Redis 7
├── .gitignore
└── README.md
```

## API 参考

### 端点一览

| 端点 | 方法 | Content-Type | 说明 |
|---|---|---|---|
| `/healthz` | GET | — | 健康检查（返回 PG / Redis 连接状态） |
| `/research` | POST | `application/json` | 非流式：提交主题，返回完整报告 |
| `/research/stream` | POST | `application/json` | **SSE 流式**：实时推送研究进度事件 |
| `/sessions` | GET | — | 历史会话列表（最近 20 条） |
| `/sessions/{id}` | GET | — | 指定会话详情（含所有子任务） |

### SSE 实时事件

前端通过 `/research/stream` 端点接收以下事件流，实时渲染研究进度：

| 事件类型 | 触发时机 | 携带数据 |
|---|---|---|
| `status` | 各阶段状态变更 | `message` 状态描述文本 |
| `todo_list` | Planner 完成规划 | `tasks` 子任务列表（含标题、意图、关键词） |
| `task_status` | 子任务状态变更 | `task_id` / `status` / `summary` / `sources` |
| `critic_result` | Critic 评审完成 | `score` 评分 / `feedback` 改进建议 / `iteration` 轮次 |
| `final_report` | 最终报告生成 | `report` Markdown 完整报告 / `session_id` |
| `done` | 全流程结束 | — |

### 流式请求示例

```bash
curl -N -X POST http://localhost:8000/research/stream \
  -H "Content-Type: application/json" \
  -d '{"topic":"2025年AI Agent技术发展趋势"}'
```

## License

MIT © [lhh737](https://github.com/lhh737)
