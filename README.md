# XHS Multi-Agent Creator

一个基于多智能体架构的小红书内容创作平台，自动生成高质量的小红书文案和配图。访问 👉：http://47.100.107.192:3000/ 可以直接通过IP访问

## 📖 项目简介

本项目采用多智能体协作架构：编排层负责意图识别、执行路径规划与内容 brief；Copywriter、Image、Reviewer 等专业 Agent 协同完成平台内容的创作、配图和审核。

## 🏗️ 技术架构

### 应用架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    前端层 (React + TypeScript + Vite)             │
│  ┌───────────────────────────────────────────────────────────┐   │
│  │ UI Components │ API Services │ SSE Client │ Virtual List │   │
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
│  │  Trigger: Push to feat-init branch or v* tags                │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │   │
│  │  │  Checkout    │→│  Build Images│→│  Push to Aliyun  │   │   │
│  │  │  Code        │  │  (Backend)   │  │  Container       │   │   │
│  │  └──────────────┘  └──────────────┘  │  Registry (ACR)  │   │   │
│  │                                      └──────────────────┘   │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │   │
│  │  │ Vite Build   │→│  Nginx Image │→│  Push to Aliyun  │   │   │
│  │  │ dist Assets  │  │  (Frontend)  │  │  Container       │   │   │
│  │  └──────────────┘  └──────────────┘  │  Registry (ACR)  │   │   │
│  │                                      └──────────────────┘   │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │   │
│  │  │ Next Build   │→│ Standalone   │→│ Push to Aliyun   │   │   │
│  │  │ Share Pages  │  │  Image       │  │ Container        │   │   │
│  │  └──────────────┘  └──────────────┘  │ Registry (ACR)   │   │   │
│  │                                      └──────────────────┘   │   │
│  └──────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────┬────────────────────────────┘
                                         │ SSH Deploy
┌────────────────────────────────────────▼────────────────────────────┐
│                        阿里云服务器部署                              │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Docker Compose Orchestration                                │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │   │
│  │  │   Backend    │  │   Frontend   │  │ Frontend Share   │   │   │
│  │  │   :8000      │  │   :3000      │  │     :3001        │   │   │
│  │  │ Share Store  │  │ Nginx Proxy  │  │ Next Standalone  │   │   │
│  │  └──────────────┘  └──────────────┘  └──────────────────┘   │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

### CI/CD 工作流

| 阶段 | 工具/平台 | 说明 |
|------|-----------|------|
| **代码托管** | GitHub | 源代码版本控制 |
| **CI 构建** | GitHub Actions | 自动化构建和测试 |
| **镜像仓库** | 阿里云 ACR | 容器镜像存储（上海区域） |
| **CD 部署** | GitHub Actions + SSH | 自动部署到阿里云服务器 |
| **容器编排** | Docker Compose | 多容器服务管理 |
| **反向代理** | Nginx | 主前端静态资源服务，并代理 `/dialog`、`/session`、`/shares` 到后端 |
| **分享页服务** | Next.js standalone | 独立容器承载公开分享页 |


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
| **OpenAPI SSOT** | 后端 OpenAPI 作为前端 API 类型唯一事实源，`frontend-ts` 通过 `openapi-typescript` 生成类型 |
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

### 前端结构 (`frontend-ts/`)

```
frontend-ts/README.md
```

### 分享页结构 (`frontend-share/`)

```
frontend-share/README.md
```

## 🔧 技术栈

| 层级 | 技术 | 版本 |
|------|------|------|
| 后端框架 | FastAPI | ^0.100 |
| 前端框架 | React | ^19 |
| 分享页框架 | Next.js | latest |
| 前端语言 | TypeScript | ^5 |
| 前端构建 | Vite | ^8 |
| 样式框架 | Tailwind CSS | ^3 |
| 大模型框架 | LangChain | ^0.1 |
| 向量数据库 | ChromaDB | ^0.4 |
| 图片生成 | Replicate / SiliconFlow | - |
| 容器编排 | Docker Compose | - |

## 🛠️ 快速开始

### 环境要求

- Python 3.8+
- Node.js 22+（前端 Docker 构建使用 Node 22，满足 Vite 运行要求）
- Docker & Docker Compose

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

在 `frontend-ts` 中配置分享页公开地址：

```env
VITE_SHARE_BASE_URL=https://share.example.com
```

在 `frontend-share` 中配置后端 API 地址：

```env
API_BASE_URL=https://api.example.com
NEXT_PUBLIC_API_BASE_URL=https://api.example.com
```

### 启动服务

**方式一：使用 Docker Compose（推荐）**

```bash
docker compose up -d
```

**方式二：本地开发**

```bash
# 启动后端
cd backend
pip install -r requirements.txt
pnpm run start

# 启动前端
cd ../frontend-ts
pnpm install
pnpm run start

# 启动公开分享页
cd ../frontend-share
pnpm install
pnpm dev
```

### 访问服务

- 门户 / 分享 / 创作台入口（`frontend-share`）：http://localhost:3000
- 门户首页：http://localhost:3000/
- 登录页：http://localhost:3000/login
- 创作台（需登录）：http://localhost:3000/studio
- 分享详情：http://localhost:3000/share/[shareId]
- 本地直连 Vite 创作端（开发调试）：http://localhost:5173/studio/
- 后端 API：http://localhost:8000

**响应：** SSE (Server-Sent Events) 流式响应

### 分享功能部署

分享功能已接入现有 Docker Compose 和 GitHub Actions 部署链路：

- 后端 `POST /shares` 保存生成结果快照，`GET /shares/{share_id}` 供公开分享页读取。
- 主创作端 `frontend-ts` 使用 `VITE_SHARE_BASE_URL` 生成分享链接，例如 `https://share.example.com/share/abc123`。
- 主前端 Nginx 已代理 `/shares` 到后端，支持生产环境从结果页创建分享快照。
- 独立分享页 `frontend-share` 使用 Next.js standalone 镜像部署，在 `docker-compose.yml` 中默认映射到 `3001:3000`。
- GitHub Actions 会构建并推送 `agents:frontend-share` 镜像，部署阶段通过 `docker compose pull && docker compose up -d` 拉起。

生产部署时请确认：

- GitHub Repository Variable `VITE_SHARE_BASE_URL` 指向分享页公开域名，供 `frontend-ts` 镜像构建时注入。
- `frontend-share` 的 `API_BASE_URL` 指向服务端可访问的后端地址；Compose 默认使用 `http://backend:8000`。
- 后端允许分享页域名跨域访问分享接口。
- `SHARE_STORE_PATH` 或默认分享数据目录已挂载持久化卷；Compose 默认挂载 `./data/shares:/data/shares`，避免重新部署后已有分享链接失效。

## 🧪 测试

```bash
# 运行后端测试
cd backend/tests
python3  test_xxxx.py
```

## 🔍 代码清理分析

可以使用 `knip` 分析前端未使用的文件和导出：

```bash
cd frontend-ts
npx knip
```

## 📊 评估

项目集成了 LangSmith 进行智能体性能评估，可通过 LangSmith 平台查看各 Agent 的执行追踪和评估结果。
### LangSmith 评估截图
<img width="3380" height="1040" alt="image" src="https://github.com/user-attachments/assets/2fd49dbd-0a9a-457c-bd9a-1190ee8943da" />

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
