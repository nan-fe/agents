---
name: feature-react-loop
description: >-
  ReAct 全栈开发循环：探索项目上下文 → 按 DB/Backend/Frontend 规划任务 →
  执行-观察-自愈 → 终检验证。Use when 开发新功能、修 bug、全栈改动、
  三层上下文、project-map、ReAct 流程，或改动 backend/frontend-share 功能代码。
---

# ReAct 全栈开发循环

编排「探索 → 规划 → 执行/观察 → 验证」四段流程，与 [`project-map` skill](../project-map/SKILL.md) 互补：

| 职责 | project-map | 本 skill |
|------|-------------|----------|
| 文档怎么写 | 负责 | 动线变更时提醒更新 doc |
| 开发前读什么 | doc 结构 | **阅读顺序 + Context Brief** |
| 改动顺序 | 三层概念 | **Task 1→2→3 + 跳过规则** |
| 改完验证 | 列出测试路径 | **跑命令 + 自愈循环** |

详细决策树与命令速查见 [reference.md](reference.md)；完整 trace 见 [examples.md](examples.md)。

---

## 何时启用

- 用户要求**新功能**、**修 bug**、**全栈改动**
- 改动涉及 `backend/`、`frontend-share/`、`project-map/` 中任一功能路径
- 用户提到 ReAct、三层上下文、project-map

**不启用**（直接改即可）：纯文档 typo、改 `.env.example` 注释、单文件格式化、用户明确说「只改一行」。

---

## 总流程

```
Explore → Plan → [Task N: Act → Observe → (Heal ×≤3)] → Final Verify → (更新 project-map)
```

每 Task 内嵌 mini ReAct：**Implement → tier-1 verify → Pass? → next / heal**

---

## 1. 探索环（Explore）

**目标**：写代码前收集上下文，输出 **Context Brief**。禁止跳过。

### 步骤

1. 读 [`project-map/README.md`](../../project-map/README.md)（全局不变量 + 功能索引）
2. 按改动路径匹配 feature doc（路由表同 [`.cursor/rules/project-map.mdc`](../../.cursor/rules/project-map.mdc)）
   - 无匹配 → 标记「新功能，Final Verify 后需按 [`template.md`](../project-map/template.md) 新建 doc」
3. 读匹配 feature doc 的三层表 +「勿做 / 常见幻觉」
4. 按涉及层读规范：
   - 后端 → [`.agents/skills/fastapi/SKILL.md`](../fastapi/SKILL.md) + [`.agents/skills/backend-ruff/SKILL.md`](../backend-ruff/SKILL.md) + [`.cursor/rules/backend-modifications.mdc`](../../.cursor/rules/backend-modifications.mdc)
   - 前端 → [`frontend-share/AGENTS.md`](../../frontend-share/AGENTS.md)
   - 根规范 → [`AGENTS.md`](../../AGENTS.md)
5. 在**相似现有代码**中确认错误处理惯例（见下方速查）
6. 输出 Context Brief（模板见下），并标注将执行/跳过的 Task

### 错误处理惯例（探索时确认）

| 层 | 惯例 | 典型位置 |
|----|------|----------|
| 前端 fetch | `fetchWithReport` + `reportError` | `src/lib/fetch-with-report.ts` · `src/services/api.ts` |
| 前端表单 | `useActionState` + Server Action | `src/lib/actions/` |
| SSE | `parseSSEStream` · `useSSEClient`；**禁止** next.config rewrite | `src/lib/sse/` · Route Handler |
| FastAPI | `HTTPException` · Pydantic 校验 · 保留类型注解 | `backend/app/main.py` · `schemas.py` |
| 测试 | `pytest -m "not network"` 默认；integration 单独标记 | `backend/tests/` |

### Context Brief 模板

复制并填写，开始 Plan 前必须输出：

```markdown
## Context Brief

- **功能边界**：[一句话 + 入口路由]
- **涉及层**：[DB | Backend | Frontend] — 跳过层及原因
- **数据源**：Prisma / Python PG / CSV·内存 / 无
- **全局不变量**：[逐条确认：双库分离 / 无 Python auth / SSE 不走 rewrite / OpenAPI 真源 / …]
- **参考文件**：[2–5 个最相似实现]
- **常见幻觉**：[来自 feature doc，2–4 条]
- **计划 Task**：[ ] Task1  [ ] Task2  [ ] Task3
```

---

## 2. 规划环（Plan）

**默认顺序**（数据流向下）：Task 1 数据源 → Task 2 后端 → Task 3 前端。

### Task 定义

| Task | 内容 | 典型路径 |
|------|------|----------|
| **Task 1** | 单一数据源 | `frontend-share/prisma/` · `backend/app/memory/` · `schemas.py` |
| **Task 2** | 后端功能 | `backend/app/main.py` · `services/` · Next.js `route.ts` / Server Action |
| **Task 3** | 前端 | `pnpm gen:api` → `src/services/api.ts` → `src/app/` 组件 |

### 层跳过

**不要机械执行三步。** 按 [reference.md § 层跳过决策树](reference.md#层跳过决策树) 决定 Task 清单，并在 Brief 中写明原因。

常见情形：

- 纯 UI 样式/文案 → 仅 Task 3
- 纯后端逻辑、无 schema 变更 → 跳过 Task 1
- 仅 Prisma/NextAuth → Task 1 + Task 3
- API 契约变更 → Task 1→2→3 全走；Task 3 前必须 `gen:api`

### Plan 输出

为每个将执行的 Task 写 checklist（可独立验证的小步）：

```markdown
## Plan

### Task 1: [名称]
- [ ] 步骤 1
- [ ] 步骤 2
- tier-1: `...`

### Task 2: ...
```

---

## 3. 执行-观察环（Act-Observe）

每个 Task 完成后**立即** tier-1 验证，再进入下一 Task。

```
Implement → tier-1 verify → Pass?
  ├─ Yes → next Task
  └─ No  → Observation（完整 stderr/stdout）→ 诊断 → 修复 → retry（max 3）
```

### 自愈协议

1. **Observation**：粘贴完整命令输出，不截断、不 paraphrase 报错
2. **Thought**：定位文件/行号，对照 Context Brief 中的不变量
3. **Act**：最小 diff 修复；不引入无关重构
4. **Retry**：重跑同一 tier-1 命令
5. **3 轮仍失败** → 停止，向用户报告：阻塞点、已尝试修复、建议下一步

### 禁止

- 凭静态阅读宣布某 Task 完成
- 跳过 tier-1 直接做下一 Task
- 无限重试

tier-1 命令见 [reference.md § Tier-1 验证](reference.md#tier-1-验证每-task-后)。

---

## 4. 验证环（Final Verify）

全部 Task 完成后跑**层终检**（见 [reference.md § Final 终检](reference.md#final-终检全部-task-后)）。

额外检查：

| 条件 | 动作 |
|------|------|
| 改动 `backend/` 或 `mcp-lark/` Python | 仓库根目录 **必跑**：`ruff check backend mcp-lark` → `ruff format backend mcp-lark`（两条都 exit 0） |
| 后端 API 变更 | backend 在 `:8000` → `cd frontend-share && pnpm gen:api` → 提交 `schema.d.ts` |
| 动线/路由/Schema 变更 | 更新 `project-map/<feature>.md` + [`README.md`](../../project-map/README.md) 索引 |
| 新功能无 doc | 按 [`project-map` skill](../project-map/SKILL.md) 新建 doc |

终检失败 → 同样走自愈协议（max 3 轮），然后报告用户。

---

## 双库路由（探索时必确认）

| 数据 | 库 | 路径 |
|------|-----|------|
| 画室账号、OAuth | Prisma PostgreSQL | `frontend-share/prisma/` |
| 创作 projects/versions | Python PostgreSQL | `backend/app/memory/` |
| 产品 RAG | 文件/向量 | `product_rag_system/data/` |

**单一数据源原则**：一个功能只选一个主数据源；跨库读写须在 Brief 中显式说明。

---

## 快速检查清单

开始编码前：

- [ ] 已读 project-map README + 匹配 feature doc
- [ ] 已输出 Context Brief
- [ ] 已确定 Task 清单（含跳过层原因）
- [ ] 已写 Plan checklist

宣布完成前：

- [ ] 每个 Task 经 tier-1 通过
- [ ] 若改动 backend/mcp-lark Python：`ruff check backend mcp-lark` 与 `ruff format backend mcp-lark` 均已通过
- [ ] Final 终检通过
- [ ] API 变更已 gen:api
- [ ] 动线变更已同步 project-map

---

## 附加资源

- [reference.md](reference.md) — 层跳过决策树、验证命令速查
- [examples.md](examples.md) — 全栈新功能 / 单层 bugfix 完整 trace
