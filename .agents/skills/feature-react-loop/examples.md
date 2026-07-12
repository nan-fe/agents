# ReAct 完整 Trace 示例

两条典型路径，展示 [`SKILL.md`](SKILL.md) 四段流程的实际输出形态。

---

## Trace A — 新功能（全栈）：新增 X 平台发布

**用户请求**：「在创作台增加 X（Twitter）发布，跟微博发布类似。」

### Explore

1. 读 `project-map/README.md` → 不变量 #3 SSE、#4 OpenAPI
2. 读 `project-map/studio-content-creation.md` → 发布动线、微博/飞书边界
3. 读 `backend/app/services/social/` 中 `weibo_publisher.py`、`x_publisher.py`（若已有）
4. 读 `frontend-share/src/app/studio/components/` 中 `result-display.tsx`

**Context Brief（节选）**

```markdown
## Context Brief

- **功能边界**：Studio 结果页增加 X 发布；入口在 result-display
- **涉及层**：DB（跳过）· Backend · Frontend
- **数据源**：无新表；复用现有 social 配置/会话模式（参考微博 SQLite + Profile）
- **全局不变量**：无 Python auth ✓ · SSE 无关 ✓ · OpenAPI 新增 endpoint → gen:api ✓
- **参考文件**：weibo_publisher.py · weibo-login-panel.tsx · api.ts 微博段
- **常见幻觉**：勿在 Python 加画室 login；勿 rewrite SSE
- **计划 Task**：[ ] Task1  [x] Task2  [x] Task3
```

**跳过 Task 1 原因**：无 Prisma/Python PG schema 变更，沿用现有 auth store 模式。

### Plan

```markdown
## Plan

### Task 2: X Publisher 后端
- [ ] `services/social/x_publisher.py` — publish + login check
- [ ] `main.py` — POST /social/x/publish、/login/start|confirm
- [ ] `tests/test_x_publisher.py`
- tier-1: `pytest tests/test_x_publisher.py -m "not network" -q`

### Task 3: 前端集成
- [ ] `pnpm gen:api`
- [ ] `api.ts` — startXLogin / confirmXLogin / publishToX
- [ ] `x-login-panel.tsx` + result-display 发布入口
- tier-1: `pnpm lint && pnpm test`
```

### Act-Observe（Task 2 示例）

**Implement** → 添加 publisher + 路由 + 测试

**tier-1**:

```bash
cd backend && pytest tests/test_x_publisher.py -m "not network" -q
```

**Observation (attempt 1/3)** — 假设失败：

```
ImportError: cannot import name 'XPublishError' from 'app.services.social.x_publisher'
```

**Fix** → 补 export 或修正 import → **Retry** → Pass ✓

### Act-Observe（Task 3）

**Implement** → gen:api + api.ts + UI

**tier-1**: `pnpm lint` → Pass ✓

### Final Verify

```bash
cd backend && pytest tests/ -m "not network" -q
cd frontend-share && pnpm lint && pnpm test && pnpm build
```

**Doc 更新**：studio-content-creation.md 发布小节增加 X 平台一行 + 动线表。

---

## Trace B — 单层 bugfix：SSE 重连 lastEventId 丢失

**用户请求**：「热点分析 SSE 断线重连后重复收到旧事件。」

### Explore

1. 读 `project-map/hotspot-analysis.md` — SSE 代理路径
2. 读 `frontend-share/AGENTS.md` — SSE 章节
3. grep `lastEventId` / `useSSEClient` / `sse-event-id.ts`

**Context Brief（节选）**

```markdown
## Context Brief

- **功能边界**：social-hotspot-analysis 组件 SSE  ingest 去重
- **涉及层**：Frontend only — 跳过 DB、Backend（代理未变）
- **数据源**：无
- **全局不变量**：SSE 走 Route Handler ✓（只修客户端 ingest）
- **参考文件**：use-sse-client.ts · sse-stream-ingest.ts · sse-event-id.ts
- **计划 Task**：[ ] Task1  [ ] Task2  [x] Task3
```

### Plan

```markdown
## Plan

### Task 3: 修复 reconnect lastEventId 传递
- [ ] `use-sse-client.ts` — reconnect 时带上 lastEventId
- [ ] `sse-stream-ingest.ts` — 确认 dedupe key 含 event id
- [ ] 补/改 `sse-event-id.test.ts` 或 sse-parser 相关测试
- tier-1: `pnpm test -- src/lib/sse/` && `pnpm lint`
```

### Act-Observe

**tier-1**:

```bash
cd frontend-share && pnpm test -- src/lib/sse/sse-parser.test.ts && pnpm lint
```

Pass ✓ → 无需 heal

### Final Verify

```bash
cd frontend-share && pnpm lint && pnpm test && pnpm build
```

**Doc**：若动线未变，可不更新 project-map；若 ingest 协议变更，更新 hotspot-analysis.md 前端层一段。

---

## 对比摘要

| | Trace A 全栈 | Trace B 单层 |
|--|-------------|--------------|
| Task 1 | 跳过 | 跳过 |
| Task 2 | 执行 | 跳过 |
| Task 3 | 执行 | 执行 |
| gen:api | 是 | 否 |
| project-map | 更新 | 可选 |
| Final | pytest 全量 + build | lint + test + build |
