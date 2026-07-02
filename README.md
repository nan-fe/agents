# XHS Multi-Agent Creator

一个基于多智能体架构的小红书内容创作平台，自动生成高质量的小红书文案和配图。访问 👉：http://47.100.107.192:3000/ 可以直接通过IP访问

飞书推送与 MCP 接入配置见 [`mcp-lark/docs/INTEGRATION.md`](mcp-lark/docs/INTEGRATION.md)。

## 📖 项目简介

本项目采用多智能体协作架构：编排层负责意图识别、执行路径规划与内容 brief；Copywriter、Image、Reviewer 等专业 Agent 协同完成平台内容的创作、配图和审核。
<img width="2032" height="1020" alt="demo" src="https://github.com/user-attachments/assets/34b1c6a3-1741-4944-982b-7b835baec841" />

#### 自动发布至微博
<img width="1682" height="1232" alt="20260701205120_rec_" src="https://github.com/user-attachments/assets/f0136a69-24db-4993-aa8a-2abd5e831e33" />

## 🏗️ 技术架构

### 应用架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    前端层 (Next.js + React + TypeScript)            │
│  ┌───────────────────────────────────────────────────────────┐   │
│  │ Portal / Auth │ Studio SPA │ Share ISR │ API Proxy/SSE  │   │
│  └───────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────┬───────────────────────────┘
                                      │ HTTP/SSE
┌─────────────────────────────────────▼───────────────────────────┐
│                        后端层 (FastAPI)                          │
│  ┌─────────────────┐  ┌──────────────────┐  ┌───────────────┐   │
│  │   API Gateway   │→│  Security Guard  │→│ Orchestrator  │   │
│  │   (main.py)     │  │ Input/Prompt Rule│  │ Agent 工作流  │   │
│  └────────┬────────┘  └──────────────────┘  └───────┬───────┘   │
│           │                                          │           │
│           │                                          ▼           │
│           │              ┌─────────────────────────────────┐    │
│           │              │     Orchestrator 编排层         │    │
│           │              │  Plan 阶段 → Execute → Repair   │    │
│           │              │  (intent / pipeline / brief)    │    │
│           │              └───────────────┬─────────────────┘    │
│           │                              │                     │
│           │              ┌───────────────▼─────────────────┐    │
│           │              │     执行 Agent 协作网络          │    │
│           │              │  RAG → Copywriter → Image       │    │
│           │              │              ↓                  │    │
│           │              │           Reviewer              │    │
│           │              └─────────────────────────────────┘    │
│           │                                                   │   │
│           │              ┌─────────────────────────────────┐    │
│           │              │         基础设施层              │    │
│           │              │  LLM Factory  │  Token Counter │    │
│           │              │  Image Service│  Search Tool    │    │
│           │              └─────────────────────────────────┘    │
│           │                                                   │   │
│           │              ┌─────────────────────────────────┐    │
│           │              │           数据层                │    │
│           │              │  ChromaDB  │  CSV Data        │    │
│           │              └─────────────────────────────────┘    │
│           └───────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### DevOps 架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                         GitHub Actions CI/CD                         │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Trigger: push / pull_request (`.github/workflows/ci.yml`)     │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │   │
│  │  │  Checkout    │→│  Build Images│→│  Push to Aliyun  │   │   │
│  │  │  Code        │  │  (Backend)   │  │  Container       │   │   │
│  │  └──────────────┘  └──────────────┘  │  Registry (ACR)  │   │   │
│  │                                      └──────────────────┘   │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │   │
│  │  │ Next Build   │→│ Standalone   │→│ Push to Aliyun   │   │   │
│  │  │ Portal+Studio│  │  Image       │  │ Container        │   │   │
│  │  │ + Share      │  │(frontend-share)│ Registry (ACR)   │   │   │
│  │  └──────────────┘  └──────────────┘  └──────────────────┘   │   │
│  └──────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────┬────────────────────────────┘
                                         │ SSH Deploy
┌────────────────────────────────────────▼────────────────────────────┐
│                        阿里云服务器部署                              │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Docker Compose Orchestration                                │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │   │
│  │  │   Backend    │  │  PostgreSQL  │  │ Frontend Share   │   │   │
│  │  │   :8000      │  │   :5432      │  │  :3000 (唯一入口) │   │   │
│  │  │ Share Store  │  │  users DB    │  │ Next Standalone  │   │   │
│  │  └──────────────┘  └──────────────┘  └──────────────────┘   │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

### CI/CD 工作流

| 阶段 | 工具/平台 | 说明 |
|------|-----------|------|
| **代码托管** | GitHub | 源代码版本控制 |
| **CI** | GitHub Actions | push/PR 触发：backend ruff + pytest、mcp-lark ruff + pytest、frontend-share lint/test/build/e2e、OpenAPI 契约检查 |
| **Pre-commit** | pre-commit + ruff | 本地提交前：ruff 格式化、变更 Python 文件 pytest、frontend-share `tsc` |
| **静态类型** | mypy | 本地可选：`bash scripts/mypy-backend.sh`（配置见根目录 `pyproject.toml`） |
| **镜像仓库** | 阿里云 ACR | 容器镜像存储（上海区域） |
| **CD 部署** | GitHub Actions + SSH | 自动部署到阿里云服务器 |
| **容器编排** | Docker Compose | 多容器服务管理 |
| **反向代理** | Next.js standalone | 唯一 Web 入口；Route Handler / rewrite 代理 API 到 backend |
| **分享页服务** | Next.js ISR | `/share/[shareId]` 公开分享页 |


## 🚀 核心能力

### 编排与执行

一轮对话分为 **Plan（规划）→ Execute（执行）→ Repair（审核修复）** 三阶段：

| 阶段 | 模块 | 职责 |
|------|------|------|
| **Plan** | `orchestrator/planning/` | 意图识别；是否重新生成内容 brief；解析执行 pipeline（refine 走规则表，新任务/换题走 LLM 路由） |
| **Execute** | `DialogOrchestratorAgent` | 按 `priority_order` 顺序调用执行 Agent，读写 `ExecutionContext` |
| **Repair** | `review_repair_router` | 审核未通过时，按失败类型规则路由修复子 pipeline（与主 Plan 分离） |

**二次对话优化**：`refine_content` / `refine_image` 仅跑必要 Agent（如文案+审核、配图+审核），复用 session 中的 plan 与上轮结果，不重复内容 brief 与全量 pipeline。

### 智能体能力

| Agent / 模块 | 职责 | 核心功能 |
|--------------|------|----------|
| **Plan 阶段**（`planning/plan_phase`） | 编排规划 | 意图分类、`priority_order` 决策、session 产物加载 |
| **Content Strategist** | 内容 brief | 按需生成创作要点（目标人群、核心卖点、语气风格、配图要求等）；不进执行 pipeline |
| **Copywriter Agent** | 文案创作 | 根据 brief 生成小红书风格文案（标题、正文、话题标签） |
| **Image Agent** | 配图生成 | 根据文案与 brief 生成配图 |
| **Reviewer Agent** | 内容审核 | 检查合规性、平台规则、风格匹配度 |
| **Product RAG Agent** | 商品检索 | 向量检索 + 关键词匹配，为文案提供商品信息 |
| **Orchestrator** | 总编排 | 协调 Plan / Execute / Repair，管理对话状态 |
| **Safety Guard** | 输入安全 | 编排前拦截 prompt injection、越权指令、空输入和高风险内容 |

### 基础设施能力

| 组件 | 功能 |
|------|------|
| **Token Counter** | 精确的Token计数和上下文窗口管理 |
| **OpenAPI SSOT** | 后端 OpenAPI 作为前端 API 类型唯一事实源，`frontend-share` 通过 `openapi-typescript` 生成 `src/api/schema.d.ts` |
| **Prompt Security Rules** | 为 Agent、意图识别、动态路由注入统一安全与权限规则 |


### 安全校验框架

在进入 Orchestrator 前完成输入安全检查。被拦截的请求不会触发后续 Agent，而是通过 SSE 返回统一的 `SAFETY_BLOCKED` 结果，并在日志流中标记为 `SafetyGuard`。

## 📁 项目结构

### 后端结构 (`backend/`)

```
backend/
├── app/
│   ├── main.py                    # FastAPI 入口、SSE 对话
│   ├── agents/
│   │   ├── copywriter_agent.py    # 文案 Agent
│   │   ├── image_agent.py         # 配图 Agent
│   │   ├── reviewer_agent.py      # 审核 Agent
│   │   ├── product_rag_system/    # 商品 RAG
│   │   └── orchestrator/          # 编排层
│   │       ├── agent.py           # DialogOrchestratorAgent
│   │       ├── planning/          # 规划子模块
│   │       │   ├── plan_phase.py           # Plan 阶段编排
│   │       │   ├── intents.py              # 意图常量与 replann 规则
│   │       │   ├── pipeline_resolver.py    # pipeline 规则 / LLM 路由
│   │       │   └── content_strategist_agent.py  # 内容 brief
│   │       ├── execution_context.py
│   │       ├── session_history.py
│   │       ├── agent_executor.py
│   │       ├── agent_input_builder.py
│   │       ├── result_mapper.py
│   │       └── review_repair_router.py
│   ├── services/
│   │   └── orchestrator_llm_service.py  # 意图识别、fresh task 路由 LLM
│   └── security/                  # 输入安全与 Prompt 规则
├── tests/
└── README.md
```

详见 [backend/README.md](backend/README.md)。

### 前端结构 (`frontend-share/`)

创作台已从 `frontend-ts`（Vite SPA）迁入 Next.js 应用，**门户、鉴权、创作台、分享页统一由 `frontend-share` 提供**。

```
frontend-share/
├── src/app/studio/          # 创作台（Client SPA，dynamic ssr:false）
├── src/app/share/           # 公开分享页（ISR）
├── src/app/dialog/generate/ # SSE Route Handler
├── src/app/product_info/    # 商品识别长超时代理
├── src/services/api.ts      # 浏览器 API + OpenAPI 类型
└── README.md                # 本地开发与部署说明
```

`frontend-ts/` 进入维护阶段，新功能请在 `frontend-share` 开发。详见 [frontend-share/README.md](frontend-share/README.md)。

### 分享页结构 (`frontend-share/`)

公开分享页与创作台同属 `frontend-share`，见 [frontend-share/README.md](frontend-share/README.md)。

## 🔧 技术栈

| 层级 | 技术 | 版本 |
|------|------|------|
| 后端框架 | FastAPI | ^0.100 |
| 前端框架 | Next.js App Router + React | latest / ^19 |
| 前端语言 | TypeScript | ^5 |
| 样式框架 | Tailwind CSS | v4（frontend-share） |
| 大模型框架 | LangChain | ^0.1 |
| 向量数据库 | ChromaDB | ^0.4 |
| 图片生成 | Replicate / SiliconFlow | - |
| 容器编排 | Docker Compose | - |

## 🛠️ 快速开始

### 环境要求

- Python **3.11+**（CI 与 `pyproject.toml` 目标版本）
- Node.js **22+**、pnpm **10+**
- Docker & Docker Compose（PostgreSQL、可选全栈 Compose）
- 可选：`pre-commit`（见下方一次性开发依赖安装）

### 一次性开发依赖（推荐）

在项目根目录执行：

```bash
pip install -r requirements-dev.txt   # ruff、mypy、pytest、pre-commit
pip install -r backend/requirements.txt
pip install -e mcp-lark                 # 飞书 OAuth / IM 集成
pre-commit install                      # 安装 git hooks（可选）
```

根目录 `requirements-dev.txt` 为**仓库级开发工具**（ruff / mypy / pytest / pre-commit），同时服务于 `backend/` 与 `mcp-lark/`；`backend/requirements.txt` 为运行时依赖。

### 配置环境变量

在 `backend/.env` 文件中配置以下环境变量：

```env
API_KEY=xxxxx
# Base URL
MODEL_BASE_URL=xxxxx

# Model
BASE_MODEL=deepseek-v4-flash

# Image Generation Model
SILICONFLOW_API_KEY=xxxx
SILICONFLOW_BASE_URL=xxx
IMAGE_MODEL=xxxx

EMBEDING_MODEL=xxxxx

# Public share
# 后端分享快照默认写入 backend/app/data/shares.json，生产环境建议配置持久化路径
SHARE_STORE_PATH=/data/xhs-multi-agent/shares.json

# LangSmith配置
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langchain_key
LANGCHAIN_PROJECT=XHS-Multi-Agent
```

在 `frontend-share/.env` 中配置（本地开发示例）：

```env
API_UPSTREAM_URL=http://localhost:8000
API_BASE_URL=http://localhost:8000
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/xhs_auth
NEXT_PUBLIC_SITE_URL=http://localhost:3000
```

生产环境浏览器 API 使用同域相对路径；容器内 SSR / Route Handler 使用 `http://backend:8000`。

### 启动服务

**方式一：使用 Docker Compose（推荐）**

```bash
docker compose up -d
```

**方式二：本地开发**

```bash
# PostgreSQL（用户鉴权）
docker compose up postgres -d

# 终端 1：后端 API（:8000）
cd backend
pip install -r requirements.txt
pip install -e ../mcp-lark
cp .env.example .env   # 填入 API Key 等
pnpm run start

# 终端 2：frontend-share（门户 + 创作台 + 分享，:3000）
cd frontend-share
pnpm install
cp .env.example .env
pnpm db:migrate:deploy
pnpm dev
```

后端也可使用 `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`（需已安装依赖）。

### 访问服务

- 唯一 Web 入口（`frontend-share`）：http://localhost:3000
- 门户首页：http://localhost:3000/
- 登录页：http://localhost:3000/login
- 创作台（需登录）：http://localhost:3000/studio
- 分享详情：http://localhost:3000/share/[shareId]
- 后端 API：http://localhost:8000

**响应：** SSE (Server-Sent Events) 流式响应

### 分享与 Web 部署

- 后端 `POST /shares` 保存生成结果快照，`GET /shares/{share_id}` 供公开分享页读取。
- 创作台在 `/studio` 内生成分享链接，使用当前站点 origin（如 `https://example.com/share/abc123`）。
- `frontend-share` 为**唯一公网 Web 入口**，Docker Compose 映射 `3000:3000`；API 经 Next rewrites / Route Handler 代理到 `backend:8000`。
- GitHub Actions 构建并推送 `agents:backend`、`agents:frontend-share`、`agents:postgres` 镜像。

生产部署时请确认：

- GitHub Actions **Secrets**：`AUTH_SECRET`、`SENTRY_DSN`
- `frontend-share` 构建期 `API_UPSTREAM_URL=http://backend:8000`；运行期 `API_BASE_URL` / `API_UPSTREAM_URL` 指向容器内 backend
- `SHARE_STORE_PATH` 或 `./data/shares` 持久化卷已挂载，避免重新部署后分享链接失效
- **不再部署** `frontend-ts` Nginx 容器；无需 `VITE_SHARE_BASE_URL` / `STUDIO_UPSTREAM_URL`

## 🧪 测试与质量检查

### 后端

```bash
cd backend
pytest tests/ -m "not network"          # 默认套件（排除 DuckDuckGo 网络测试）
```

### 仓库根目录（Python 静态检查）

```bash
ruff check backend mcp-lark
ruff format backend mcp-lark
bash scripts/mypy-backend.sh            # 或 python3 -m mypy
```

### 前端（frontend-share）

```bash
cd frontend-share
pnpm lint                               # tsc --noEmit
pnpm test                               # Vitest（SSE parser、middleware）
pnpm build                              # prisma generate + next build
pnpm test:e2e                           # Playwright 冒烟（CI 用 Postgres service）
```

### OpenAPI 类型契约

后端运行于 `:8000` 时，可校验前端类型是否与 OpenAPI 一致：

```bash
bash scripts/check-openapi-contract.sh
# 或手动：cd frontend-share && pnpm gen:api
```

### MCP Lark

```bash
cd mcp-lark
pytest tests/
```

## 🔍 代码清理分析

可以使用 `knip` 分析前端未使用的文件和导出：

```bash
cd frontend-share
npx knip
```

## 📊 评估

项目集成了 LangSmith 进行智能体性能评估，可通过 LangSmith 平台查看各 Agent 的执行追踪和评估结果。
### 文案生成 deepseek-v4-pro(A) vs deepseek-v4-flash(B)
从结构性、相关性以及语言风格对比，AI 裁判模型是 Pro/zai-org/GLM-5.1
<img width="1268" height="532" alt="image" src="https://github.com/user-attachments/assets/e16f76fc-5c05-448a-aa8c-421d1f85be2d" />
延时&成本
<img width="1258" height="530" alt="image" src="https://github.com/user-attachments/assets/e3330885-a381-4157-88f3-ead121d16976" />



## ⚠️ 已知限制

| 序号 | 限制描述 | 状态 | 计划 |
|------|----------|------|------|
| 1 | 线上环境下首次访问页面时，Chroma 数据库构建时间较长，需要等待一定时间 | 已修复 | 2026/5/10 |
| 2 | RAG 补充商品信息的效果待验证 | 待验证 | 需要收集更多测试数据进行验证 |
| 3 | 图片生成的相关性较弱 | 待优化 | 计划尝试其他图片生成模型进行比对 |
| 4 | 评估代码目前只支持文案 Agent 和 RAG Agent | 待扩展 | 其他 Agent 的系统评估方案还待探索 |

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

*Built with ❤️ using Multi-Agent Architecture*
