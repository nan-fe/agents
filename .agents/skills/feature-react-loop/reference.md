# ReAct 参考：决策树与验证命令

本文件供 [`SKILL.md`](SKILL.md) 探索/规划/验证环引用。Agent 仅在需要跳过层或选择命令时读取。

---

## 层跳过决策树

```
用户请求
│
├─ 仅改样式/文案/布局（无 API/Schema）?
│   └─ YES → 仅 Task 3（Frontend）
│
├─ 仅改 backend 内部逻辑（输入输出契约不变、无 DB migration）?
│   └─ YES → 仅 Task 2；tier-1: pytest 相关模块
│
├─ 仅改 Prisma/NextAuth/账号（不涉及 Python 创作库）?
│   └─ YES → Task 1（Prisma）+ Task 3；跳过 Task 2 Python
│
├─ 仅改 Python DB schema 或 DTO，前端暂不改?
│   └─ YES → Task 1 + Task 2；Task 3 延后（Brief 注明）
│
├─ 新增/变更 HTTP API 契约?
│   └─ YES → Task 1→2→3 全走；Task 3 前必须 gen:api
│
├─ 新增 SSE / 长连接?
│   └─ YES → Task 2 Route Handler 代理 + Task 3 hook；
│            确认不走 next.config rewrite（全局不变量 #3）
│
└─ 新功能（无现有 project-map doc）?
    └─ 全栈默认 Task 1→2→3 + Final 后新建 project-map doc
```

### 双库快速判断

| 若功能涉及… | 数据源 Task 1 |
|-------------|---------------|
| 登录、注册、用户资料 | Prisma `users` / `accounts` |
| 对话、项目、版本、分享 | Python `project_memory` |
| 选品池 | Python `product_info` 相关 |
| 热点分析 | Python `social_hotspot` 相关 |

---

## Tier-1 验证（每 Task 后）

Task 完成后**立即**运行，通过再进入下一 Task。

### Task 1 — 数据源

**Prisma 变更**

```bash
cd frontend-share
pnpm db:generate
# 若有 migration
pnpm db:migrate   # 本地开发；deploy 环境用 db:migrate:deploy
```

**Python schema / models 变更**

```bash
cd backend
pytest tests/test_<相关模块>.py -m "not network" -q
python -c "from app.models.schemas import <符号>"   # 快速 import 检查
```

**仅改 schemas.py DTO（无 migration）**

```bash
ruff check backend mcp-lark
ruff format backend mcp-lark
cd backend
python -c "from app.models.schemas import <符号>"
```

### Task 2 — 后端

**每次 Task 2 完成后先跑 Ruff**（仓库根目录，两条都须 exit 0）：

```bash
ruff check backend mcp-lark
ruff format backend mcp-lark
```

再跑测试：

```bash
cd backend
pytest tests/test_<相关模块>.py -m "not network" -q
```

影响面大（路由、编排器）时：

```bash
cd backend
pytest tests/ -m "not network" -q
```

**Next.js Route Handler / Server Action**（无 Python 变更）

```bash
cd frontend-share
pnpm lint
pnpm test -- src/<相关>.test.ts   # 若有对应 Vitest
```

### Task 3 — 前端

**API 契约已在 Task 2 变更**（backend 须在 `:8000` 运行）：

```bash
cd frontend-share
pnpm gen:api
pnpm lint
pnpm test
```

**仅 UI / 无 API 变更**：

```bash
cd frontend-share
pnpm lint
pnpm test
# 可选：pnpm test -- src/lib/sse/sse-parser.test.ts 等定向测试
```

---

## Final 终检（全部 Task 后）

按改动范围选**最小充分**命令集：

| 改动范围 | 命令 |
|----------|------|
| 仅 backend / mcp-lark Python | `ruff check backend mcp-lark` → `ruff format backend mcp-lark` → `cd backend && pytest tests/ -m "not network" -q`（mcp-lark 另跑 `cd mcp-lark && pytest tests/ -q`） |
| 仅 frontend | `cd frontend-share && pnpm lint && pnpm test && pnpm build` |
| 全栈 | 上述 Ruff + backend pytest 全量 + frontend lint/test/build |
| API 契约变更 | 上述 + `pnpm gen:api`；确认 `schema.d.ts` diff 合理 |

**Ruff 注意**：Final 阶段也用 `ruff format`（写盘修复），不要用 `--check`；CI 才用 `--check`。

### OpenAPI 契约（API 变更时）

```bash
# 终端 1：backend
cd backend && uvicorn app.main:app --reload --port 8000

# 终端 2：生成类型
cd frontend-share && pnpm gen:api
```

或仓库根目录：

```bash
bash scripts/check-openapi-contract.sh
```

### E2E（可选，PR 前 / 动线大改）

```bash
cd frontend-share && pnpm test:e2e
```

默认 CI 不跑 network/integration 测试；勿移除 `-m "not network"` 除非用户明确要求。

---

## 自愈 Observation 格式

验证失败时，下一轮 Thought 应引用：

```markdown
## Observation (attempt N/3)

**Command**: `...`
**Exit code**: N

\`\`\`
<完整 stdout/stderr>
\`\`\`

**Hypothesis**: ...
**Fix**: ...
```

---

## project-map 路径 → 文档

| 改动路径（摘要） | 先读 |
|------------------|------|
| login/register/auth/middleware/user-service | `project-map/auth-login-register.md` |
| studio 对话/generate/orchestrator/project_memory | `project-map/studio-content-creation.md` |
| product-pool/product_info | `project-map/product-pool.md` |
| social-hotspot-analysis/social-hotspots | `project-map/hotspot-analysis.md` |
| 未列出 | 新建 `project-map/<slug>.md` + 更新 README 索引 |

---

## 全局不变量速查

来自 [`project-map/README.md`](../../project-map/README.md)：

1. 双库分离（Prisma 账号 vs Python 创作库）
2. 无 Python auth（NextAuth 管 session；Python 只收 `user_id`）
3. SSE/长请求走 Route Handler，**禁止** next.config rewrite
4. OpenAPI → `schema.d.ts`（`pnpm gen:api`）
5. 前端无 Redux/Zustand（`useActionState` / hooks / session）
6. Studio `user_id` = `getStudioUserId(session)`
7. 分享页 `/share/[shareId]` 与登录无关
8. 改功能同步 project-map doc
