# Project Map 文档模板（极简版）

对齐 [`auth-login-register.md`](../../project-map/auth-login-register.md)。复制下方到 `project-map/<slug>.md`，替换占位符。目标 ~100–130 行。

---

```markdown
# [功能中文名]

[一句话能力描述]。

**入口**：[路由 / 侧栏 Tab]

> **边界**：[排除的相邻功能]，见 [其它文档](其它文档.md)。

---

## Agent 阅读指引

> 通用规范：[`project-map` skill](../.agents/skills/project-map/SKILL.md) · 索引：[`README.md`](README.md)

| 层级 | 关注点 | 路径 |
|------|--------|------|
| 数据库 | [表/文件/缓存，或「无持久化」] | `[路径]` |
| 后端 | [路由、服务、DTO] | `[路径]` |
| 前端 | [页面、组件、代理] | `[路径]` |

状态：[useActionState / useSession / SSE hook 等] · 无 Redux/Zustand。

---

## 用户动线

（mermaid flowchart，节点 ID 无空格）

| 操作 | 调用链 |
|------|--------|
| [操作] | `[METHOD] /path` 或 `fn()` → … |

[一两句补充：缓存、自动触发、失败回退]

---

## 数据库层

[无 SQL 时写：**本功能无** PostgreSQL/Prisma 表；说明 CSV / 内存缓存 / 文件]

（Schema 树或一两行字段摘要 · 迁移表若有 · 读写函数名）

---

## 后端层

| 方法 | 路径 | 说明 |
|------|------|------|
| | | |

（一段主路径 flow，勿重复动线表）

DTO：[Schema 名]（`schemas.py`）关键字段

---

## 前端层

（组件路径树，单行或短列表）

| 状态 | 位置 |
|------|------|
| | |

API：`services/api.ts` / Server Action / Route Handler（SSE 须 Handler，勿 rewrite）

---

## 勿做 / 常见幻觉

- 勿 [本功能特有误判 1]
- 勿 [本功能特有误判 2]
- 勿 [跨功能/global 误判，可引用 README 不变量]

---

## 测试

| 类型 | 位置 |
|------|------|
| E2E | |
| 后端 | |
```

---

## 编写后必做

1. 更新 [`project-map/README.md`](../../project-map/README.md) 功能索引与「改功能 → 先读 doc」表
2. 视需要扩展 [`.cursor/rules/project-map.mdc`](../../.cursor/rules/project-map.mdc) globs

---

## 三层调研命令（勿写入 feature doc）

```bash
# 数据库
rg "model " frontend-share/prisma/
rg "CREATE TABLE|append_version|\.csv" backend/ product_rag_system/

# 后端
rg "@app\.(get|post|put|delete|patch)" backend/app/main.py
rg "class.*BaseModel" backend/app/models/schemas.py
rg "route\.ts" frontend-share/src/app/

# 前端
rg "from '@/services/api'|useActionState|useSession|useSSEClient" frontend-share/src/
```
