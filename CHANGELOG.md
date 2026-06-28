# Changelog

All notable changes to this project will be documented in this file.

### Changed 2026-06-25 — 历史删除、用户隔离与 SSE 复用安全

- **历史对话删除**
  - 后端新增 `DELETE /projects/{project_id}?user_id=`，删除 project 行及全部 versions（处理 `parent_version_id` 自引用 FK）
  - 创作台历史抽屉每条记录支持删除，带二次确认；删除当前对话自动进入新空白页，删除其他对话不影响当前会话

- **projects / versions 按 user_id 隔离**
  - `versions` 表新增 `user_id` 字段；启动时自动迁移已有 SQLite 库（[`backend/app/memory/db.py`](backend/app/memory/db.py)）
  - `ProjectMemoryService` 新增 `project_accessible()`；列表、读取、finalize、删除均校验 `user_id + project_id` 归属，非本人返回 404
  - `append_version` 写入时保存 `user_id`，并回填 `projects.user_id`
  - 前端 Studio 全链路传递 `userId`（session 的 `username` 或 `id`）：项目 API、finalize、SSE 生成请求

- **SSE 流复用安全**
  - `DialogStream` 增加 `user_id`、`project_id` 并持久化；复用/续传时校验 **sessionId + userId + userInput + projectId**（不再仅比 `session_id + prompt`）
  - 修复换账号后同 prompt 误复用上一用户生成结果的问题
  - 进行中的相同请求改为订阅已有 stream，避免 cancel 后重复跑 pipeline
  - 退出登录时清除 `xhs_session_id` / `xhs_project_id`（[`logout/page.tsx`](frontend-share/src/app/logout/page.tsx) 替代原 Route Handler）

- **生成失败错误提示**
  - 扩展 `classify_agent_failure` / 新增 `format_agent_failure_message`，网络/鉴权/上游错误不再统一显示 `UNKNOWN`
  - dialog 生成 fallback 重试补齐 `user_id`、`project_id`；失败时记录完整 traceback

- **测试**
  - 新增 `test_dialog_stream_reuse.py`；更新 `test_project_api.py`、`test_project_memory.py` 覆盖用户隔离与删除
  - 重新生成 `frontend-share/src/api/schema.d.ts`

### Changed 2026-06-22 — 后端稳定性、类型检查与 OAuth 修复

- **后端启动修复**
  - Agent 基类与子类中将错误的 `callable | None` 类型注解改为 `Callable | None`，修复 Python 3.11+ 下 uvicorn 无法 import 应用、导致「新对话」等 `/projects` API 不可用的问题

- **mypy 静态检查（可选，本地/渐进采用）**
  - 根目录 `requirements-dev.txt` 增加 `mypy`
  - `pyproject.toml` 新增 `[tool.mypy]`（范围 `backend/app`，`mypy_path` 含 `mcp-lark`）
  - 新增 `scripts/mypy-backend.sh`；说明见 `AGENTS.md`

- **Copywriter Agent**
  - `run()` 先将 `PlanningResult | dict` 统一归一为 `planning_dict`，再 `.get()` 取值；避免 `PlanningResult` 对象路径误读不存在的 `user_input` 属性，并与 dict 主路径行为一致

- **飞书 OAuth**
  - `seed_studio_default_client` 在 `redirect_uris` 为空时改为抛出 `ValueError`，返回类型收窄为 `LarkOAuthClientRow`，与 `ensure_studio_default_client` 声明一致

- **文档**
  - `README.md` 更新本地开发、CI/pre-commit、mypy 与测试命令

### Changed 2026-06-19 — 创作台迁入 frontend-share（frontend-ts → Next.js）

将主创作台从 Vite SPA（`frontend-ts`）合并进 Next.js 应用（`frontend-share`），**统一门户、鉴权、创作台、分享页于同一域名与端口**，降低双前端维护成本。迁移目标为 Client SPA 迁入 App Router，而非 SSR 化创作台。

- **frontend-share（创作台 `/studio`）**
  - 新增 `src/app/studio/`：`studio-app` 壳层、对话流（`dialog-content`）、选品池、项目历史抽屉、结果分享等，自 `frontend-ts` 迁入
  - `/studio` 入口使用 `dynamic(() => import('./studio-app'), { ssr: false })`，避免 `sessionStorage` / `window` 在 SSR 阶段报错
  - 新增共享层：`src/services/api.ts`、`src/lib/sse/*`、`src/types/conversation.ts`、`src/theme/atelier-theme.ts`
  - Ant Design 根节点 `<ConfigProvider><App>` 包裹；`modal.confirm` / `message` 改走 `App.useApp()`
  - 修复停止生成后按钮状态不恢复、SSE `disconnect` 无法中断重连循环、`App.useApp()` 误用于 plain async 函数等问题
  - 生产环境浏览器 API 使用同域相对路径（`API_BASE_URL=""`）；分享链接基于 `window.location.origin` 生成

- **API 与代理（仍由 frontend-share 接管）**
  - `/dialog/generate`：`app/dialog/generate/route.ts` SSE 流式透传（不可用普通 rewrite，会缓冲日志）
  - `/product_info/*`：`app/product_info/[...path]/route.ts` 长超时代理
  - `/projects`、`/session`、`/shares`：`next.config.mjs` rewrite → `API_UPSTREAM_URL`

- **部署**
  - `docker-compose.yml` 移除 `frontend`（Vite + Nginx）服务；仅保留 `postgres`、`backend`、`frontend-share`
  - GitHub Actions 停止构建 `frontend-ts` 镜像，CI 只构建并推送 `frontend-share`
  - 移除 `/studio` → Vite 的 Next rewrite；**无需**将 `frontend-ts/nginx.conf` 迁移到 Next 镜像
  - `frontend-share` 继续使用 `output: 'standalone'`，容器内 `prisma migrate deploy && node server.js`

- **frontend-ts**
  - 进入维护/退役阶段；新功能在 `frontend-share` 开发。本地开发默认只需启动 `backend` + `frontend-share`

**迁移注意事项（编写）**：Client Component 仍会 SSR 一次；Hooks 不可在 async 工具函数中调用；Tailwind v4 与 Vite v3 工具链不同；import 路径优先使用 `@/` alias。

**迁移注意事项（部署）**：`API_UPSTREAM_URL` 需在镜像**构建期**传入（rewrites 固化）；Route Handler 与 SSR 在**运行期**读取同名变量；`POST /shares` 需精确 rewrite（`/shares/:path*` 不匹配无子路径请求）。

### Changed 2026-06-11 — PR1：编排短期记忆（L1）

为内容创作对话补充 **L1 短期记忆**：在现有 `session_histories` + `ExecutionContext` 状态机之上，增加 SQLite 持久化的 `projects` / `versions` 表，使多轮对话可跨刷新恢复、可在历史项目中切换。

- **后端（`backend/app/memory/`）**
  - 新增 `projects`、`versions` ORM 与 `ProjectMemoryService`：`versions` 在每次成功生成后即时写入；`projects` 在页面关闭（`pagehide` beacon）或侧栏「新对话」时通过 `finalize` 汇总写入
  - 新增 API：`GET /projects`、`POST /projects`、`GET /projects/{project_id}`、`POST /projects/finalize`
  - 编排器绑定 `project_id`，内存会话为空时从 DB 水合；成功结果返回 `project_id` / `version_id` / `version`
  - `updated_at` 表示内容最近变更；`last_accessed_at` 表示用户最近打开，历史列表按后者降序
  - `UTCDateTime` 类型修复 SQLite 读回无时区导致的前端时间偏差

- **前端（`frontend-ts`）**
  - `localStorage` 持久化 `project_id` + `session_id`；首屏拉取项目列表并恢复最近打开的对话
  - 侧栏「新对话」：finalize 当前项目 → 新建 session + project
  - 顶栏历史抽屉：按 `last_accessed_at` 展示项目列表，点击切换并加载 `versions` 重建线程
  - `parseApiDateTime` 统一将 API UTC 时间转本地展示

- **部署**
  - `docker-compose.yml` 挂载 `./data/memory`，`DATABASE_URL=sqlite+aiosqlite:////data/memory/memory.db`

### Changed 2026-06-11 — PR1.1：会话驱逐与列表查询优化

- **空闲驱逐**：`SESSION_IDLE_TTL_SECONDS`（默认 30 分钟）；`WritingSessionHistory.last_active_at` + `session_eviction`；访问新 session 时惰性清理；进行中的 SSE 生成会话不驱逐
- **`GET /projects`**：`version_counts` 批量聚合，消除 N+1

- 编排器解析 `project_id` 后调用 `ensure_project_stub`（与 `POST /projects` 行为对齐，幂等）

**PR1.1 仍待补充**

- L2 长期记忆（跨项目用户偏好）与项目 JSON 索引

### Changed 2026-06-02

- **Atelier 视觉与设计系统（`frontend-ts` / `frontend-share`）**
  - 统一 Art Deco + 油画质感「创作画室」主题：Cinzel / Cormorant Garamond、`atelier-*` 组件与 Tailwind 色板（`frontend-ts/src/theme/`、`index.css`、`globals.css`）
  - `frontend-share` 首页、登录/注册、分享页、404 与错误页接入同一套面板与装饰样式；`layout` 使用 `next/font` 加载字体
  - 新增 `frontend-share/src/lib/format.ts`、`frontend-ts/src/utils/format.ts`：`Intl.DateTimeFormat` 统一时间展示

- **Studio 对话体验重构（`frontend-ts`）**
  - 布局改为窄侧栏 + 居中对话流 + 底部输入区（类 DeepSeek）；侧栏「新对话」通过 `resetSessionId()` 重置会话并 remount `DialogContent`
  - 对话线程模型：`welcome` / `turn` / `pending` 按时间顺序渲染；每轮用户气泡与助手回复分离，生成结果独立内容面板
  - 新增 `chat-avatar`、`chat-message`、`conversation-turn`、`pending-turn`；版本选择器 + `version-anchor-*` 滚动定位
  - 退出登录改为侧栏 `<a href="/logout">`，移除顶栏按钮

- **思考过程展示**
  - 生成中与完成后均可查看 Agent 日志；完成后写入 `TurnThreadItem.logs` 持久化
  - 柔和辅助样式面板 + Step 时间线；展开/收起使用上下箭头；滚动区自动跟随最新日志
  - `agent-logs` 移除 Ant Design Collapse，改为自定义嵌入式折叠

- **可访问性与交互规范**
  - Skip link、`main` 地标、`aria-live`、表单 label、`prefers-reduced-motion`、`:focus-visible` 等 Web Interface Guidelines 项落地
  - `result-display` 分享链使用 `useActionState`；`session.ts` 统一管理 `session_id`

- **LangSmith 可观测性（后端）**
  - `llm_factory` 支持 `agent_name` / `prompt_version` / `model_name` metadata；结构化解析成功/失败上报 `parse_success` feedback
  - Copywriter、Reviewer、编排意图/路由调用补齐版本标记
  - `pipeline_resolver`：`@traceable` 包裹 `resolve_pipeline`；fallback 路由上报 LangSmith `fallback_route` feedback

- **分享门户与登出**
  - `frontend-share` `/logout` 同时支持 `GET` 与 `POST`，修复创作台 `location.assign('/logout')` 返回 405

- **评测脚本**
  - `evaluate_copywriter.py` 评估 LLM 改为 SiliconFlow `GLM-5.1` 配置

### Changed 2026-05-31

- **编排层 Planner / Router 职责收敛**
  - 新增 `orchestrator/planning/pipeline_resolver.py`：`refine_content` / `refine_image` 走规则表固定短链，不再调用 LLM 路由；`new_task` / `change_topic` 仍走 `route_task`

- **规划模块目录收拢与命名澄清**
  - 原 `PlannerAgent` 重命名为 **ContentStrategistAgent**（内容 brief，非编排 pipeline 规划）
  - 规划相关代码迁入 `backend/app/agents/orchestrator/planning/`：
    - `plan_phase.py` — Plan 阶段（intent → brief → pipeline）
    - `intents.py` — 意图常量、`should_run_content_strategist` 等规则
    - `content_strategist_agent.py` — 内容策划 LLM
    - `pipeline_resolver.py` — 执行路径解析

- **测试**
  - 新增 `test_pipeline_resolver.py`、`test_orchestrator_llm_service.py`（路由 Prompt 约束）
  - 原 `test_planner_agent.py` 更名为 `test_content_strategist_agent.py`

### Changed 2026-05-23

- **分享页 ISR**
  - `frontend-share` 的 `/share/[shareId]` 由动态 SSR 调整为 ISR
- **Better Stack 错误监控**
  - `frontend-share` 接入 `@sentry/nextjs`，通过 Better Stack Sentry 兼容 DSN 上报客户端/服务端错误
  - 新增 `global-error.tsx`、分享页 `error.tsx` 自动 `captureException`；Docker / Compose / CI 支持 `SENTRY_DSN` 注入

### Changed 2026-05-22

- **use the react 19 hooks in frontend-ts**
- **add login&registry feature**

### Changed 2026-05-20

- **前端 SSE 日志渲染优化**
  - 新增 `useBatchedState` hook：将高频 state 更新先入队，按约 50ms 节流后在 `requestAnimationFrame` 中合并应用，降低 SSE 流式推送 Agent 日志时的重复渲染

### Changed 2026-05-17

- **公开分享功能**
  - 新增后端 `/shares`、`/shares/{share_id}` 快照接口，用于保存和读取生成结果的公开分享内容
  - `frontend-ts` 结果展示区支持生成分享链接，并通过 `VITE_SHARE_BASE_URL` 拼接公开分享页地址
  - 新增独立 Next.js 应用 `frontend-share`，提供 `/share/[shareId]` 公开分享页、社交预览 metadata、复制链接、复制文案和社交平台跳转
  - 分享快照默认写入 `backend/app/data/shares.json`，生产部署可通过 `SHARE_STORE_PATH` 配置持久化路径
  - `frontend-share` 开启 Next.js standalone 输出，新增容器镜像、Docker Compose 服务和 GitHub Actions 构建推送步骤
  - 主前端 Nginx 新增 `/shares` 代理，支持生产环境创建分享快照；`frontend-ts` Docker 构建支持注入 `VITE_SHARE_BASE_URL`

### Changed 2026-05-16

- **前端 API 类型 SSOT**
  - `frontend-ts` 接入后端 OpenAPI 作为接口类型唯一事实源，通过 `openapi-typescript` 生成 `src/api/schema.d.ts`
  - 新增 `pnpm run gen:api`，支持在后端启动后重新生成前端接口类型

- **输入安全校验**
  - 新增进入编排前拦截空输入、prompt injection、越权指令与高风险内容
  - 安全拦截通过 SSE 返回 `SAFETY_BLOCKED`、`safety_category` 与可读提示，并记录 `SafetyGuard` 日志
  - 新增 `prompt_rules.py`，向 Agent、意图识别和路由提示词注入共享安全与权限规则

### Changed 2026-05-15

- **超时与重试逻辑修正**
  - 编排层意图识别、动态路由的超时与降级统一收敛到 `OrchestratorLLMService`（`wait_for` + 编排专用 HTTP 重试次数），`agent.py` 不再分散维护 `asyncio.wait_for`


- **前端结果展示**
  - `result-display` 在无正文时回退展示 `result.message`，便于展示超时、部分失败等提示

### Changed 2026-05-14

- **分级超时与可观测性**
  - `config` 增加各 Agent / 编排 LLM 超时配置（意图、路由、Planner、Copywriter、Image、Reviewer、RAG 等）

- **RAG 启动**
  - 后台预热 Chroma 索引

- **策略化 HTTP 重试与部分成功**
  - 新增 `retry_policy.py`：`is_transient_exception`、指数退避 + 抖动

### Changed 2026-05-13

- **前端稳定性与性能优化**
  - SSE 流式处理增加重连能力，降低网络抖动导致生成流程中断的概率
  - 聊天记录面板改为虚拟列表渲染，减少历史消息较多时的 DOM 数量和页面卡顿

- **前端构建与部署升级**
  - `frontend-ts` 增加 Vite 打包能力，开发启动和生产构建改为使用 `vite`
  - 生产构建产物由 `build` 调整为 `dist`
  - Docker 前端镜像构建同步适配 Vite 输出目录，并使用 Nginx 承载静态资源和代理后端接口
  - Vite 构建优化（`feat: vite add css opt`）：`cssMinify: lightningcss`、`minify: oxc`、`cssCodeSplit`、资源内联阈值等；`ANALYZE=true` 时可生成 `dist/stats.html` 包体分析

### Changed 2026-05-10

- **会话管理优化** 
  - 前端：使用 sessionStorage 持久化会话 ID，确保同一标签页内会话一致
  - 后端：`DialogOrchestratorAgent` 改为全局单例模式，会话历史不再因请求而重置
  - 修复 `refine_content`｜`refine_image` 时无法读取历史规划和结果的问题

- ** 重构 orchestrator **
  - *** 重构遵循单一职责原则和开闭原则 ***
    - 按照功能拆分文件
  - ***WritingSessionHistory 重构***
    - 使用独立字段 `_last_result` 和 `_last_plan` 存储状态，替代之前复杂的消息队列查找
  - ***ExecutionContext 优化*** 
    - 延迟构建 `history_data`，按需生成历史数据字符串
    - 移除 `set_history_data()` 方法，改为 `set_last_result()` + `get_history_data()` 组合
    - 节省内存，避免重复存储
  - ***重试策略移除*** 
    - 异常直接抛出，由上层处理

- **refactor the rag sys & change the base model** 
  - 按照功能拆分文件
  - 更换基础模型，从硅基流动换成商汤最后换成 DeepseekV4

