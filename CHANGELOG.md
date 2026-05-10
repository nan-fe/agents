# Changelog

All notable changes to this project will be documented in this file.

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

