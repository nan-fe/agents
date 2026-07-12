# Project Map 索引

单功能 Agent 参考文档。改动功能代码前**必须先读**本页对应 doc（见下方路由表）。

编写规范：[`.agents/skills/project-map/SKILL.md`](../.agents/skills/project-map/SKILL.md) · 开发流程：[`.agents/skills/feature-react-loop/SKILL.md`](../.agents/skills/feature-react-loop/SKILL.md) · 范例：[`auth-login-register.md`](auth-login-register.md)

---

## 功能索引

| 文档 | 功能 | 入口 |
|------|------|------|
| [`auth-login-register.md`](auth-login-register.md) | 登录 / 注册 | `/login` · `/register` |
| [`studio-content-creation.md`](studio-content-creation.md) | 主创作台对话与发布 | `/studio` → 内容生成 |
| [`product-pool.md`](product-pool.md) | 选品池 | `/studio` → 选品池 |
| [`hotspot-analysis.md`](hotspot-analysis.md) | 热点分析 | `/studio` → 热点分析 |

---

## 全局不变量（跨功能）

1. **双库分离**：画室账号在 `frontend-share` Prisma PostgreSQL；创作项目/版本在 Python 后端 PostgreSQL。
2. **无 Python auth**：登录/注册/session 全在 NextAuth；Python 只收 `user_id`（= `username`），不验 session。
3. **SSE / 长请求**：必须走 Next.js Route Handler 代理，**禁止**在 `next.config` rewrite（会缓冲断流）。
4. **API 类型真源**：后端 OpenAPI → `frontend-share/src/api/schema.d.ts`（`pnpm gen:api`）。
5. **前端状态**：用 `useActionState` / hooks / NextAuth session；**无** Redux/Zustand。
6. **Studio 用户标识**：`getStudioUserId(session)` → 后端 `user_id`。
7. **分享页**：`/share/[shareId]` 读 `GET /shares/{id}`，与登录无关。
8. **改功能同步 doc**：动线、路由、Schema 变更时更新对应 `project-map/*.md`。

---

## 改功能 → 先读 doc

| 改动路径（glob 摘要） | 先读 |
|----------------------|------|
| `frontend-share/src/app/login/**` · `register/**` · `auth*.ts` · `middleware.ts` · `lib/user-service.ts` | [`auth-login-register.md`](auth-login-register.md) |
| `frontend-share/src/app/studio/components/dialog-content.tsx` · `dialog/generate/**` · `backend/**/orchestrator/**` · `project_memory` | [`studio-content-creation.md`](studio-content-creation.md) |
| `product-pool.tsx` · `product_info/**` · `backend/**/product_info*` | [`product-pool.md`](product-pool.md) |
| `social-hotspot-analysis.tsx` · `social-hotspots/**` · `backend/**/social_hotspot/**` | [`hotspot-analysis.md`](hotspot-analysis.md) |

未列出的新功能：按 [`template.md`](../.agents/skills/project-map/template.md) 新建 `project-map/<slug>.md` 并更新本索引。
