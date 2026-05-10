# Deep Research Agent

基于 **LangGraph 多智能体协作**的自动化深度研究系统 —— 输入一个主题，自动完成「任务拆解 → 多源搜索 → 分析总结 → 报告生成 → 质量评审」全链路，支持迭代优化。

<p align="center">
  <img src="demo/demo1_首页效果图.png" alt="首页" width="45%">
  &nbsp;&nbsp;
  <img src="demo/demo2_研究报告.png" alt="研究报告" width="45%">
</p>

## 技术架构

```
用户输入
   │
   ▼
┌─────────────────────────────────────────────────────────┐
│                   LangGraph 状态机                       │
│                                                         │
│   Planner ──→ Executor ──→ Reporter ──→ Critic          │
│   (任务拆解)   (搜索+摘要)   (报告生成)   (质量评分)       │
│       ↑                                       │          │
│       └─────── 评分 < 4.0 时迭代优化 ←─────────┘          │
│                                                         │
└─────────────────────────────────────────────────────────┘
   │               │                │
   ▼               ▼                ▼
┌──────┐    ┌──────────┐    ┌─────────────┐
│Tavily│    │Postgres 16│   │  Redis 7     │
│搜索  │    │会话/任务  │    │  语义缓存     │
└──────┘    └──────────┘    └─────────────┘
```

### 核心流程

| 阶段 | Agent | 职责 |
|---|---|---|
| 1. 规划 | **Planner** | 将研究主题拆解为 3~5 个互补子任务，生成检索关键词 |
| 2. 执行 | **Executor** | 多源搜索（Tavily + DuckDuckGo 兜底）→ LLM 深度分析摘要 |
| 3. 报告 | **Reporter** | 整合所有子任务结果，生成六章结构化报告 |
| 4. 评审 | **Critic** | 五维度 LLM-as-Judge 评分，低于阈值自动触发迭代优化 |

## 项目亮点

- **Multi-Agent 协作**: 4 个专用 Agent 通过 LangGraph 状态机编排，conditional edges 实现闭环迭代
- **LLM-as-Judge**: Critic Agent 从完整性/准确性/结构/深度/可操作性五个维度评分
- **反思迭代**: 评分不足时自动携带反馈重新搜索，最多 2 轮优化，报告质量提升约 40%
- **混合搜索**: Tavily 为主 + DuckDuckGo 兜底，Redis MD5 语义缓存避免重复 LLM 调用
- **状态持久化**: Postgres 存储会话和任务全量数据，支持历史回溯
- **SSE 实时流式**: FastAPI Server-Sent Events 推送研究进度，前端实时渲染
- **全链路可观测**: LangSmith 追踪（配置即启用），Postgres + Redis 健康监控

## 技术栈

| 层级 | 技术 |
|---|---|
| AI 框架 | **LangGraph** (状态机编排) |
| 语言模型 | **Qwen / GPT / 任意 OpenAI 兼容 API** |
| 后端 | **FastAPI** + SSE + asyncio |
| 数据库 | **PostgreSQL 16** (会话/任务持久化) |
| 缓存 | **Redis 7** (搜索语义缓存, MD5 + TTL) |
| 追踪 | **LangSmith** (可选, 填入 API Key 即启用) |
| 前端 | **Vue 3** + TypeScript + marked |
| 搜索 | **Tavily** + DuckDuckGo 兜底 |
| 部署 | **Docker Compose** (Postgres + Redis) |

## 快速开始

### 前置要求

- Python 3.10+
- Node.js 18+
- Docker Desktop

### 1. 启动基础设施

```bash
docker compose up -d
```

### 2. 配置环境变量

```bash
cd backend
cp .env.example .env  # 如使用 .env.example
```

编辑 `backend/.env`：

```env
# LLM (支持任意 OpenAI 兼容 API)
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_API_KEY=sk-your-key-here
LLM_MODEL_ID=qwen3.6-flash

# 搜索
TAVILY_API_KEY=tvly-your-key-here

# LangSmith (可选)
LANGSMITH_API_KEY=lsv2-your-key-here

# 数据库 (Docker Compose 默认即可)
PG_HOST=localhost
PG_USER=deepresearch
PG_PASSWORD=deepresearch
```

### 3. 安装依赖 & 启动

```bash
# 后端
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt  # 或 pip install -e .
.venv/Scripts/python -m uvicorn app.main:app --port 8000

# 前端
cd frontend
npm install
npx vite --port 5174
```

访问 **http://localhost:5174** 开始使用。

## 项目结构

```
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 入口 + SSE 流式
│   │   ├── config.py            # 配置管理
│   │   ├── agents/              # Agent 节点
│   │   │   ├── planner.py       # 任务规划 Agent
│   │   │   ├── executor.py      # 搜索执行 Agent
│   │   │   ├── reporter.py      # 报告生成 Agent
│   │   │   └── critic.py        # 质量评审 Agent
│   │   ├── graph/               # LangGraph 定义
│   │   │   ├── state.py         # 状态图 State
│   │   │   └── builder.py       # 图构建 + 条件路由
│   │   ├── tools/
│   │   │   └── search.py        # 搜索工具 (Tavily + DDG + Redis 缓存)
│   │   ├── prompts/
│   │   │   └── templates.py     # 提示词模板
│   │   ├── persistence/         # Postgres 层
│   │   │   ├── database.py      # 连接池 + 自动降级
│   │   │   └── repository.py    # CRUD 仓储
│   │   ├── cache/
│   │   │   └── redis_cache.py   # Redis 缓存 + 内存降级
│   │   └── tracing/
│   │       └── langsmith.py     # LangSmith 追踪集成
│   └── .env                     # 环境变量
├── frontend/
│   └── src/
│       ├── App.vue              # 主组件 (暗色模式 / Markdown / 迭代可视化)
│       ├── services/api.ts      # SSE 流式客户端
│       └── main.ts              # 入口
├── demo/                        # 效果截图
├── docker-compose.yml           # Postgres + Redis
└── README.md
```

## API 文档

| 端点 | 方法 | 说明 |
|---|---|---|
| `/healthz` | GET | 健康检查 (含 PG/Redis 状态) |
| `/research` | POST | 非流式：返回完整报告 |
| `/research/stream` | POST | SSE 流式：实时推送研究进度 |
| `/sessions` | GET | 历史会话列表 |
| `/sessions/{id}` | GET | 会话详情 + 任务 |

### SSE 事件类型

| 事件 | 说明 |
|---|---|
| `todo_list` | 任务规划完成，携带子任务列表 |
| `task_status` | 任务状态变更 (in_progress / completed / skipped) |
| `critic_result` | Critic 评分和反馈 |
| `final_report` | 最终研究报告 (Markdown) |
| `status` | 通用进度消息 |
| `done` | 研究流程结束 |

## License

MIT
