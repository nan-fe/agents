# Changelog

All notable changes to this project will be documented in this file.

### Changed 2026-05-13

- **前端稳定性与性能优化**
  - SSE 流式处理增加重连能力，降低网络抖动导致生成流程中断的概率
  - 聊天记录面板改为虚拟列表渲染，减少历史消息较多时的 DOM 数量和页面卡顿

- **前端构建与部署升级**
  - `frontend-ts` 增加 Vite 打包能力，开发启动和生产构建改为使用 `vite`
  - 生产构建产物由 `build` 调整为 `dist`
  - Docker 前端镜像构建同步适配 Vite 输出目录，并使用 Nginx 承载静态资源和代理后端接口

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

