# Frontend Share

`frontend-share` 是 XHS Multi-Agent Creator 的 **对外 Web 入口**：门户首页、注册登录鉴权、公开分享页，以及受保护的主创作台路由 `/studio`。

## 功能

- 门户首页 `/`：介绍项目能力，引导注册、登录或进入创作台
- 注册页 `/register`：创建账号（数据写入 PostgreSQL）
- 登录页 `/login`：Auth.js Credentials 账号密码登录
- 受保护创作台 `/studio`：未登录自动跳转 `/login`，登录后 rewrite 到 `frontend-ts`
- 公开分享页 `/share/[shareId]`：展示已生成的小红书图文内容
- 自动生成 `/robots.txt`、Open Graph / Twitter metadata
- 支持复制分享链接、复制文案、分享到 X 和微博

## 技术栈

- Next.js App Router
- Auth.js (`next-auth` v5 beta)
- Prisma + PostgreSQL（用户账号存储）
- React
- TypeScript
- Tailwind CSS

## 本地开发

### 1. 启动 PostgreSQL

```bash
# 在项目根目录
docker compose up postgres -d

# 执行数据库迁移
cd frontend-share
pnpm db:migrate:deploy
```

### 2. 启动依赖服务

```bash
# 终端 1：后端
cd backend
pnpm run start

# 终端 2：主创作端（Vite，base=/studio/）
cd frontend-ts
pnpm install
pnpm run dev

# 终端 3：门户 + 鉴权入口
cd frontend-share
pnpm install
cp .env.example .env
pnpm dev
```

### 3. 访问地址


| 地址                                      | 说明                  |
| --------------------------------------- | ------------------- |
| `http://localhost:3000/`                | 门户首页                |
| `http://localhost:3000/register`        | 注册页                 |
| `http://localhost:3000/login`           | 登录页                 |
| `http://localhost:3000/studio`          | 创作台（需登录，**必须走此入口**） |
| `http://localhost:3000/share/[shareId]` | 公开分享页               |


首次使用请先在 `/register` 注册账号，再登录进入创作台。

## 环境变量


| 变量                         | 说明                                                   | 默认值                                                      |
| -------------------------- | ---------------------------------------------------- | -------------------------------------------------------- |
| `AUTH_SECRET`              | Auth.js JWT 签名密钥，生产必填                                | dev 下未设置时用内置开发密钥；已设置则用 `.env.local` 中的值                  |
| `DATABASE_URL`             | PostgreSQL 连接串                                       | `postgresql://postgres:postgres@localhost:5432/xhs_auth` |
| `STUDIO_UPSTREAM_URL`      | 创作台 upstream，Next rewrite 目标                         | `http://localhost:5173`                                  |
| `API_UPSTREAM_URL`         | 后端 upstream，供 `/dialog`、`/session`、`/shares` rewrite | `http://localhost:8000`                                  |
| `API_BASE_URL`             | 分享页 SSR 请求后端地址                                       | `http://localhost:8000`                                  |
| `NEXT_PUBLIC_API_BASE_URL` | 浏览器可见后端 API 地址                                       | `http://localhost:8000`                                  |
| `NEXT_PUBLIC_SITE_URL`     | 站点公网根地址（不带尾部 `/`）                                    | 未配置则省略 Host                                              |


示例：

```bash
cp .env.example .env
# 编辑 AUTH_SECRET、DATABASE_URL 后
pnpm dev
```

生成 `AUTH_SECRET`：

```bash
openssl rand -base64 32
```

本地 dev 二选一即可：

- **不设置** `AUTH_SECRET`：使用内置开发密钥
- **设置固定值**（`openssl rand -base64 32`）：写入 `.env.local`；修改后需清 cookie 并重新登录

勿同时跑多个 `pnpm dev`（例如 3000 与 3001 各一个），`localhost` cookie 会共用，密钥不一致时会反复出现本错误。

### 故障排查：`JWTSessionError` / `no matching decryption secret`

表示浏览器里的 session cookie 是用**另一套** `AUTH_SECRET` 签名的（常见于修改了 `.env`、复制了占位符、或 3000/3001 双实例密钥不一致）。middleware 会自动清除无效 cookie；**刷新一次**后应不再报错，然后重新登录即可。

处理方式（任选其一）：

1. 刷新页面（无效 cookie 会被清除），再重新登录
2. 手动清除 `localhost` 站点 cookie 后重新登录
3. 结束占用 3000 端口的旧 `next dev` 进程，只保留一个实例
4. 在 `.env.local` 中设置固定密钥：`openssl rand -base64 32`，重启 `pnpm dev` 后再登录

## 鉴权架构

```text
用户 → frontend-share (Next.js)
         ├─ /、/login、/register、/share/*   公开
         ├─ middleware 校验 session
         ├─ /studio/*                        rewrite → frontend-ts (/studio/)
         └─ /dialog|/projects|/session|/shares rewrite → backend

PostgreSQL (users 表)
         ↑ 注册写入 / 登录校验
Prisma ← NextAuth Credentials provider
```

- 用户账号存储在 PostgreSQL `users` 表，密码以 bcrypt 哈希保存
- 会话由 Auth.js 写入 HttpOnly Cookie（JWT strategy，30 天）
- `frontend-ts` 生产环境不应公网直连，仅通过 `/studio` 访问
- 后端 API 用户级鉴权可在后续阶段接入；当前主要保护创作台入口

## 数据库命令

```bash
pnpm db:migrate        # 开发环境创建/应用迁移
pnpm db:migrate:deploy # 生产/CI 应用迁移
pnpm db:push           # 快速同步 schema（仅开发调试）
pnpm db:generate       # 重新生成 Prisma Client
```

## 构建与部署

```bash
cd frontend-share
pnpm install
pnpm build
pnpm start
```

`next.config.mjs` 已开启 `output: 'standalone'`，适合容器化部署。容器启动时会自动执行 `prisma migrate deploy`。

Docker Compose 中：

- `postgres` 提供用户数据库
- `frontend-share` 作为唯一公网入口，默认映射 `3000:3000`
- `frontend`（创作端 Nginx）仅内网暴露，由 `STUDIO_UPSTREAM_URL=http://frontend:80` 接入
- 生产环境在 GitHub **Settings → Secrets and variables → Actions** 配置 `AUTH_SECRET`（`openssl rand -base64 32` 生成）；CI 部署时会写入服务器 `/root/agents/.env`
- 错误监控：在 Actions **Secrets** 配置 `SENTRY_DSN`（Better Stack DSN）；CI 构建 `frontend-share` 镜像时注入，**无需**在服务器 `.env` 配置
- 建议修改 Compose 中 PostgreSQL 默认密码，且勿将 `5432` 对公网开放

```bash
docker compose pull
docker compose up -d
```

`postgres` 使用与业务镜像相同的阿里云 ACR：`agents:postgres`（CI 在 GitHub 上从官方 `postgres:16-alpine` 同步推送，服务器无需访问 docker.io）。

## 错误监控（Better Stack + Sentry SDK）

通过 [@sentry/nextjs](https://docs.sentry.io/platforms/javascript/guides/nextjs/) 将错误上报至 [Better Stack Errors](https://betterstack.com/docs/errors/collecting-errors/sentry-sdk/)（Sentry 兼容 DSN）。

**生产环境**（仅需 GitHub Actions，不用改服务器 `.env`）：

| 位置 | 名称 | 值 |
|------|------|-----|
| Actions **Secrets** | `SENTRY_DSN` | Better Stack 完整 DSN |
| Actions **Variables**（可选） | `SENTRY_APPLICATION_ID` | 默认 `frontend-share` |

CI 构建镜像时同时注入 `SENTRY_DSN` 与 `NEXT_PUBLIC_SENTRY_DSN`（同一值），并写入最终镜像环境变量，部署后客户端与服务端均可上报。

**本地开发**在 `frontend-share/.env` 中配置（**勿提交真实 token**）：

```bash
SENTRY_DSN=https://YOUR_TOKEN@s2461160.eu-nbg-2.betterstackdata.com/2461176
NEXT_PUBLIC_SENTRY_DSN=https://YOUR_TOKEN@s2461160.eu-nbg-2.betterstackdata.com/2461176
```

- 未配置 DSN 时 SDK 自动 `enabled: false`，不影响本地开发

本地验证：配置 DSN 后 `pnpm build && pnpm start`，访问任意会触发错误的页面，在 Better Stack **Errors** 面板查看上报。

## 文件说明


| 文件                        | 职责                                       |
| ------------------------- | ---------------------------------------- |
| `prisma/schema.prisma`    | 用户表模型                                    |
| `src/auth.ts`             | Auth.js 配置与 Credentials provider         |
| `src/middleware.ts`       | 保护 `/studio`，处理 `/login`、`/register` 重定向 |
| `src/lib/user-service.ts` | 注册、登录凭据校验                                |
| `src/lib/prisma.ts`       | Prisma Client 单例                         |
| `src/app/login/`          | 登录页                                      |
| `src/app/register/`       | 注册页                                      |
| `next.config.mjs`         | `/studio` 与 API rewrite 规则               |


