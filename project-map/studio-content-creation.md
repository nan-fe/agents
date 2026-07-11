# 主创作台 · 多轮对话创作与发布

「内容生成」Tab：多轮对话迭代小红书图文，版本切换，分享页，可选微博/X 发布与飞书推送。

**入口**：`/studio` → 侧栏「内容生成」（`PageMenu.DIALOG_CONTENT`）

> **边界**：选品池、热点分析、微博登录设置见各自 project-map doc。

---

## Agent 阅读指引

> 通用规范：[`project-map` skill](../.agents/skills/project-map/SKILL.md) · 索引：[`README.md`](README.md)

| 层级 | 关注点 | 路径 |
|------|--------|------|
| 数据库 | `projects` · `versions`（Python PostgreSQL） | `backend/app/memory/project_memory.py` |
| 后端 | SSE `/dialog/generate` · 编排器 · projects/shares | `backend/app/main.py` · `agents/orchestrator/` |
| 前端 | `dialog-content.tsx` · SSE hook · session/project id | `frontend-share/src/app/studio/` · `app/dialog/generate/` |

状态：`ThreadItem[]` + `useSSEClient` · `session_id`/`project_id` in storage · 无 Redux/Zustand。

---

## 用户动线

```mermaid
flowchart TD
    A[/studio 内容生成] --> B[bootstrap 恢复]
    B --> C[发送 prompt]
    C --> D[SSE dialog/generate]
    D --> E[result 新版本]
    E --> C
    E --> F[分享 POST /shares]
    F --> G[/share/id]
    E -.-> H[可选：微博/X/飞书]
```

| 操作 | 调用链 |
|------|--------|
| 进入 / 恢复 | `GET /projects` → `GET /projects/{id}` |
| 首条发送 | `POST /projects` → SSE `POST /dialog/generate` |
| 继续多轮 | 同 `session_id` + `project_id` |
| 新对话 | `POST /projects/finalize` → 新 session + project |
| 分享 | `POST /shares` → `/share/{shareId}` |
| 发微博 | `POST /social/publish/weibo` → 轮询 job |
| 发 X | `POST /social/publish/x` → 轮询 job（Playwright Profile） |
| 连接 X（OAuth） | `POST /social/x/oauth/start` → Profile 内授权 → `confirm` |
| 连接 X（手动） | `POST /social/x/login/start` → 浏览器登录 → `confirm`（OAuth 未配置时） |
| 关页 | `sendBeacon` → `POST /projects/finalize` |

---

## 数据库层

```
projects       project_id, user_id, topic, final_version, project_summary, last_accessed_at …
versions       version_id, project_id, parent_version_id, intent, user_input, result JSONB …
weibo_auth     Playwright Profile 登录确认（单例）
x_auth         X Playwright Profile 登录确认（按 Studio user_id）
x_user_tokens  X OAuth token（身份绑定；发帖仍走 Playwright Web UI）
```

- 微博登录态：`weibo_auth`（Playwright Profile 单例）
- X 登录态：`x_auth`（Profile Cookie）+ 可选 `x_user_tokens`（OAuth 身份）
- **connected** = OAuth token 有效 ∧ Profile 已登录（OAuth 未配置时仅看 Profile）

- 每轮成功 → `append_version` 即时落库
- `finalize_project` → 汇总进 `projects` 行
- 列表仅展示有 version 且已 finalize 的项目

---

## 后端层

| 方法 | 路径 | 作用 |
|------|------|------|
| GET/POST/DELETE | `/projects` … | CRUD + finalize |
| POST | `/dialog/generate` | SSE 多 Agent 生成 |
| POST/GET | `/shares` … | 分享快照 |
| POST | `/social/publish/weibo` | 异步发微博（Playwright） |
| POST/GET/DELETE | `/social/x/oauth/*` | X OAuth + Profile 连接 |
| POST/DELETE | `/social/x/login/*` | X 手动 Profile 登录（fallback） |
| POST | `/social/publish/x` | 异步发 X（Playwright Web UI） |
| POST | `/lark/push-review` | 飞书推送 |

```
POST /dialog/generate
  → dialog_stream_store（新建/续传/复用）
  → orchestrator.run → append_version → SSE log/result
```

意图（节选）：`new_task` · `refine_content` · `refine_image` · `ask_question`（不写 version）

DTO `UserInput`：`prompt` · `session_id` · `project_id` · `user_id` · `last_event_id`

SSE 事件：`log` · `meta` · `result`（支持 `last_event_id` 续传）

---

## 前端层

```
studio/page.tsx · studio-app.tsx · components/dialog-content.tsx
conversation-turn · pending-turn · result-display · social-sync-settings · x-oauth-connect-panel · x-login-panel
lib/session.ts · project-conversation.ts · hooks/use-sse-client.ts
app/dialog/generate/route.ts          SSE 代理，不可 rewrite
app/share/[shareId]/page.tsx          ISR 公开页
services/api.ts
```

| 标识 | 存储 | 作用 |
|------|------|------|
| `session_id` | session/local `xhs_session_id` | SSE stream · 编排内存 |
| `project_id` | session/local `xhs_project_id` | versions 归属 |

`getStudioUserId(session)` → API `user_id`。退出登录 `clearStudioSession()` 防串号。

---

## 勿做 / 常见幻觉

- 勿把 `/dialog/generate` SSE 走 `next.config` rewrite
- 勿在 Python 后端做画室 session 校验（见 `auth-login-register.md`）
- 勿把 OAuth access_token 注入 Playwright 发 X（微博 / X 均用 Profile 浏览器）
- 勿把选品池/热点分析逻辑塞进 `dialog-content.tsx`

---

## 测试

| 类型 | 位置 |
|------|------|
| E2E | `e2e/login-studio.spec.ts` · `e2e/helpers/dialog.ts` |
| 后端 | `test_social_publish_api.py` · `test_x_login_api.py` · `test_x_publisher.py` · `test_lark_push_api.py` |
