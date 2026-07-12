---
name: backend-ruff
description: >-
  改动 backend/ 或 mcp-lark/ Python 后必跑 Ruff，与 CI 一致。
  Use when 修改 backend Python、mcp-lark、FastAPI 路由、Pydantic schema、
  pytest 前验证、或用户提到 ruff / CI lint 失败。
---

# Backend Ruff 验证

每次改动 `backend/` 或 `mcp-lark/` 的 `.py` 文件后，**在声称完成或提交前**必须在仓库根目录执行以下两条命令：

```bash
ruff check backend mcp-lark
ruff format backend mcp-lark
```

## 规则

1. **两条都要跑**，且都须 exit 0。
2. **顺序**：先 `check`，再 `format`（format 会写盘）。
3. **范围**：始终包含 `backend` 与 `mcp-lark`（与 README / CI 一致），不要只跑 `ruff check backend`。
4. **本地用 `ruff format`**（自动修复）；CI 用 `ruff format --check`（只检查不写盘）。
5. 可自动修复的 lint：`ruff check backend mcp-lark --fix`，然后重跑上面两条。

## 与 ReAct 循环的关系

- **Task 2 tier-1**：实现后立即跑 Ruff，再跑 pytest。
- **Final Verify**：全栈或仅 backend 改动时再次跑 Ruff，确保无遗漏。
- 详见 [`.agents/skills/feature-react-loop/reference.md`](../feature-react-loop/reference.md)。

## 常见 CI 失败原因

| 现象 | 处理 |
|------|------|
| `ruff check` 报 unused import / 规则违规 | `ruff check backend mcp-lark --fix` 或手改后重跑 |
| `ruff format --check` 失败 | 本地跑 `ruff format backend mcp-lark`，提交格式化 diff |
| 只跑了 check 没跑 format | 补跑 `ruff format backend mcp-lark` |

## 禁止

- 凭静态阅读跳过 Ruff
- 只跑 `ruff check backend`（漏掉 mcp-lark 或 format）
- 用 `ruff format --check` 代替 `ruff format` 作为本地终检（不会修复文件）
