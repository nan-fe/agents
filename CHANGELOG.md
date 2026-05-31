# Changelog

All notable changes to this project will be documented in this file.

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

