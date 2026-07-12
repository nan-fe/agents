# 登录 / 注册

账号密码 + 可选 GitHub/Google OAuth。认证在 `frontend-share`（NextAuth + Prisma + PostgreSQL）；Python 后端无 auth API，仅接收 `user_id`（= `username`）做项目隔离。

**入口**：`/` · `/login` · `/register` · 未登录访问 `/studio` → middleware 重定向 `/login`

> **边界**：创作台「微博登录」「飞书 OAuth」为社交集成，非画室账号体系。

---

## Agent 阅读指引

> 通用规范：[`project-map` skill](../.agents/skills/project-map/SKILL.md) · 索引：[`README.md`](README.md)

| 层级 | 关注点 | 路径 |
|------|--------|------|
| 数据库 | `users` / `accounts`、迁移 | `frontend-share/prisma/` |
| 后端 | NextAuth、Server Action、`user-service`；Python 仅 `user_id` DTO | `src/auth*.ts`、`lib/user-service.ts`；`backend/app/models/schemas.py` |
| 前端 | 登录/注册页、middleware、会话 | `src/app/login|register|logout/`、`middleware.ts` |

状态：`useActionState`（表单）· JWT Cookie（`auth()` / `useSession()`）· 无 Redux/Zustand。

---

## 用户动线

```mermaid
flowchart TD
    A[/] --> B{已登录?}
    B -->|是| C[/studio]
    B -->|否| D[/login 或 /register]
    D --> E{方式}
    E -->|密码| F[表单]
    E -->|OAuth| G[第三方授权]
    F -->|注册| H[registerAction 写库 → 自动 signIn]
    F -->|登录| I[signIn credentials]
    G --> J[findOrCreateOAuthUser]
    H --> K[JWT Cookie]
    I --> K
    J --> K
    K --> L[returnUrl 默认 /studio]
    C --> M[/logout → signOut /]
```

| 操作 | 调用链 |
|------|--------|
| 注册 | `registerAction` → `registerUser` → `signIn('credentials')`（失败则回 `/login`） |
| 登录 | `signIn('credentials')` → `verifyUserCredentials` |
| OAuth | `signIn(provider)` → `/api/auth/*` → `findOrCreateOAuthUser` |
| 守卫 | middleware：`/studio` 需登录；已登录跳过 `/login` `/register` |
| 退出 | `clearStudioSession` + `signOut({ redirectTo: '/' })` |

OAuth 用户无 `passwordHash`；首次授权自动建 `User`+`Account`（可按 email 合并已有用户）。

---

## 数据库层

PostgreSQL（`DATABASE_URL`），与 Python `projects`/`versions` **分离**。

```
users       id PK · username UNIQUE · password_hash? · email? UNIQUE · name? · image?
accounts    user_id FK→users CASCADE · provider+provider_account_id UNIQUE · OAuth tokens…
```

| 迁移 | 变更 |
|------|------|
| `20250523120000_init_users` | 建 `users` |
| `20250621120000_oauth_accounts` | `password_hash` 可空；建 `accounts` |

读写：`registerUser` · `verifyUserCredentials` · `findOrCreateOAuthUser`（`lib/user-service.ts`）

---

## 后端层

### Next.js（主路径）

| 入口 | 文件 |
|------|------|
| `/api/auth/*` | `src/app/api/auth/[...nextauth]/route.ts` |
| 注册 Server Action | `src/lib/actions/register-action.ts` |
| 配置 | `auth.ts`（providers）· `auth.config.ts`（JWT 30 天 callbacks） |
| 守卫 | `middleware.ts`（无效 cookie 清除 · `/studio` 307） |

校验：账号 `^[a-zA-Z0-9_]{3,32}$` · 密码 ≥6 位 · bcrypt 12（`lib/password.ts`）

```
注册  registerAction → registerUser → 客户端 signIn
登录  signIn → authorize: verifyUserCredentials → jwt/session 写入 id/username
OAuth signIn callback → findOrCreateOAuthUser（Account → email 合并 → 新建）
```

### Python（关联契约）

无 login/register。`getStudioUserId(session)` → `username` 作为 `user_id` 传入 `UserInput` / `ProjectCreateRequest` / projects query；仅校验非空，不验 session。

环境变量：`DATABASE_URL` · `AUTH_SECRET` · `AUTH_GITHUB_*` · `AUTH_GOOGLE_*`

---

## 前端层

```
app/page.tsx · login/{page,login-form} · register/{page,register-form} · logout/page
studio/studio-app.tsx (SessionProvider) · components/oauth-sign-in-buttons.tsx · middleware.ts
```

| 状态 | 位置 |
|------|------|
| 表单 pending/error | `login-form` / `register-form`（`useActionState`） |
| 注册后自动登录 | `register-form`（`useEffect` + credentials ref） |
| 会话 | 门户 `auth()` · 创作台 `useSession()` |

认证不走 `services/api.ts`（Python REST）。登录后 `user_id` 注入见 `studio-content-creation.md`。OAuth 按钮由 `oauth-providers.ts` 按 env 启用。

---

## 勿做 / 常见幻觉

- 勿在 Python 后端加 `/login` `/register` 或 session 校验
- 勿用 `services/api.ts` 做画室登录
- 勿引入 Redux/Zustand
- 勿把微博/飞书 OAuth 当成画室账号体系

---

## 测试

| 类型 | 位置 |
|------|------|
| E2E | `e2e/login-studio.spec.ts` · `e2e/helpers/auth.ts` |
| 单元 | `src/middleware.test.ts` |
