---
name: project-map
description: >-
  Read or write project-map/ feature docs using the three-layer context model
  (database, backend, frontend). Use when改动功能代码、梳理动线、沉淀 project-map 文档、
  Agent 需理解单功能全栈上下文，或用户提到 project-map / 三层上下文。
---

# Project Map 功能文档

`project-map/` 存放**单一功能** Agent 速查文档（每篇 ~100–130 行，极简高密度）。

- **索引 + 全局不变量**：[`project-map/README.md`](../../project-map/README.md)
- **范例**：[`auth-login-register.md`](../../project-map/auth-login-register.md)
- **开发流程（ReAct）**：[`feature-react-loop` skill](../feature-react-loop/SKILL.md) — 探索 → 规划 → 执行/自愈 → 验证
- **Cursor 自动触发**：[`.cursor/rules/project-map.mdc`](../../.cursor/rules/project-map.mdc)

---

## 核心原则：三层上下文

改动或文档化功能前，Agent **必须**同时理解三层：

| 层级 | 必须回答的问题 | 典型路径（本仓库） |
|------|----------------|-------------------|
| **数据库层** | 表/文件/缓存？约束？读写入口？ | `frontend-share/prisma/` · `backend/app/memory/` · `product_rag_system/data/` |
| **后端层** | 路由/Handler？DTO？核心业务链？ | `backend/app/main.py` · `schemas.py` · `services/` · Next.js `route.ts` / Server Action |
| **前端层** | 入口组件树？状态在哪？API 封装？ | `frontend-share/src/app/` · `services/api.ts` · `hooks/` |

**双库**：账号 → frontend-share Prisma；创作 projects/versions → Python PostgreSQL。

**状态**：如实写 `useActionState` / `useSession` / SSE hook 等；无 Redux/Zustand 时明确写出。

---

## 阅读工作流（改代码）

1. 读 [`project-map/README.md`](../../project-map/README.md)（全局不变量 + 路由表）
2. 读匹配的 feature doc（按三层理解）
3. 改代码；动线/路由/Schema 变更时**同步更新**该 doc + README 索引（若新功能）

---

## 编写工作流（写/更新 doc）

1. **定边界** — 一句话 + `> **边界**`（链到其它 doc）
2. **走读代码** — 数据库 → 后端 → 前端（见 [template.md](template.md) 调研命令）
3. **写极简 doc** — 对齐范例结构；无数据的层写「本功能无…」
4. **勿做锚点** — 2–4 条本功能常见幻觉
5. **补测试** — 只列仓库中真实存在的路径
6. **更新 README** — 新 doc 加入功能索引与路由表

---

## 文档结构（与范例一致）

```markdown
# [功能名]
[一句话] + **入口** + > **边界**

## Agent 阅读指引
（链 skill + README · 三层表 · 状态一行）

## 用户动线
（mermaid + | 操作 | 调用链 | 表）

## 数据库层
## 后端层
## 前端层

## 勿做 / 常见幻觉
## 测试
```

各层用**表格 + 一段 flow**，避免重复动线表已写过的内容。完整占位模板见 [template.md](template.md)。

---

## 检查清单

- [ ] 单功能聚焦；相邻功能仅边界引用
- [ ] 三层均已填；无数据层已说明原因（Prisma / CSV / 内存缓存等）
- [ ] 含「勿做 / 常见幻觉」2–4 条
- [ ] 测试路径真实存在
- [ ] 新 doc 已更新 [`README.md`](../../project-map/README.md)
- [ ] 篇幅 ~100–130 行（复杂 SSE 协议可略超，但不恢复冗长 prose）

---

## 现有文档

见 [`project-map/README.md`](../../project-map/README.md) 功能索引。
