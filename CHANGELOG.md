# Changelog

All notable changes to this project will be documented in this file.

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

