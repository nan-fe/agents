# Frontend Share

`frontend-share` 是 XHS Multi-Agent Creator 的 **唯一 Web 入口**：门户首页、注册登录、创作台（`/studio`）、公开分享页，以及后端 API 的同域代理。

## 功能

- 门户首页 `/`：介绍项目能力，引导注册、登录或进入创作台
- 注册页 `/register`、登录页 `/login`：Auth.js Credentials + PostgreSQL
- 创作台 `/studio`：多智能体对话、SSE 流式生成、选品池、项目历史（自 `frontend-ts` 迁入，Client SPA + `ssr: false`）
- 公开分享页 `/share/[shareId]`：ISR 展示已生成的小红书图文
- 同域 API 代理：`/projects`、`/session`、`/shares`（rewrite）、`/dialog/generate` 与 `/product_info/*`（Route Handler）

## 技术栈

- Next.js App Router（`output: 'standalone'`）
- Auth.js (`next-auth` v5 beta) + Prisma + PostgreSQL
- React 19 + React Compiler + TypeScript
- Tailwind CSS v4 + Ant Design 6

## 本地开发

### 1. 启动 PostgreSQL

```bash
# 项目根目录
docker compose up postgres -d

cd frontend-share
pnpm install
cp .env.example .env
pnpm db:migrate:deploy
```

### 2. 启动后端与 Next

```bash
# 终端 1：后端 API
cd backend
pnpm run start

# 终端 2：frontend-share（门户 + 创作台 + 分享）
cd frontend-share
pnpm dev
```

本地开发时，创作台 API 默认直连 `http://localhost:8000`（见 `src/services/api.ts`）；生产环境浏览器请求同域相对路径，经 Next 代理到后端。

### 3. 访问地址

| 地址 | 说明 |
| --- | --- |
| `http://localhost:3000/` | 门户首页 |
| `http://localhost:3000/register` | 注册 |
| `http://localhost:3000/login` | 登录 |
| `http://localhost:3000/studio` | 创作台（需登录） |
| `http://localhost:3000/share/[shareId]` | 公开分享页 |

首次使用请先在 `/register` 注册，再登录进入 `/studio`。

> `frontend-ts`（Vite）已进入维护阶段，**本地开发不再要求**并行启动 `:5173`。如需对照旧实现，可单独 `cd frontend-ts && pnpm dev`。

## 环境变量

| 变量 | 说明 | 默认值 / 建议 |
| --- | --- | --- |
| `AUTH_SECRET` | Auth.js JWT 签名密钥，**生产必填** | dev 未设置时用内置密钥 |
| `DATABASE_URL` | PostgreSQL 连接串 | `postgresql://postgres:postgres@localhost:5432/xhs_auth` |
| `API_UPSTREAM_URL` | 后端 upstream（rewrites + Route Handler） | `http://localhost:8000` |
| `API_BASE_URL` | 分享页 SSR 拉取 `/shares/{id}` | `http://localhost:8000` |
| `NEXT_PUBLIC_SITE_URL` | 站点公网根地址（metadata / 可选分享链接） | `http://localhost:3000` |
| `SENTRY_DSN` / `NEXT_PUBLIC_SENTRY_DSN` | Better Stack 错误监控 | 生产由 CI 注入 |
| `SENTRY_ORG` | Better Stack 团队 ID（SourceMap 上传） | Errors → Applications → Advanced settings |
| `SENTRY_PROJECT` | Better Stack 应用 ID（SourceMap 上传） | 默认可用 `SENTRY_APPLICATION_ID` |
| `SENTRY_URL` | SourceMap 上传端点 | 如 `https://us-east-9-sourcemaps.betterstackdata.com` |
| `SENTRY_AUTH_TOKEN` | Telemetry API token（**仅构建期**，勿提交仓库） | GitHub Secret |

生成 `AUTH_SECRET`：

```bash
openssl rand -base64 32
```

勿同时跑多个 `pnpm dev`（如 3000 与 3001），`localhost` cookie 共用会导致 `JWTSessionError`。

## 架构

```text
用户 → frontend-share (Next.js :3000)
         ├─ /、/login、/register、/share/*     公开页面
         ├─ middleware 保护 /studio
         ├─ /studio/*                            app/studio（dynamic ssr:false）
         ├─ /dialog/generate                     Route Handler → backend（SSE 透传）
         ├─ /product_info/*                      Route Handler → backend（长超时）
         └─ /projects、/session、/shares       rewrite → backend

PostgreSQL ← Prisma ← NextAuth Credentials
backend:8000 ← API_UPSTREAM_URL / API_BASE_URL（容器内网）
```

- 浏览器生产环境：`API_BASE_URL=""`，请求走同域 Next，不直连后端公网地址
- 分享链接：运行时 `window.location.origin` + `/share/{id}`
- 后端 API 用户级鉴权可在后续阶段接入；当前 middleware 主要保护 `/studio`

## 构建与部署

```bash
cd frontend-share
pnpm install
pnpm build
# standalone 产物：
node .next/standalone/server.js
```

Docker Compose（项目根目录）：

```bash
docker compose pull
docker compose up -d
```

服务组成：

| 服务 | 说明 |
| --- | --- |
| `postgres` | 用户账号库 |
| `backend` | FastAPI + 编排 |
| `frontend-share` | **唯一公网 Web 入口** `:3000` |

生产环境：

- 镜像构建期传入 `API_UPSTREAM_URL=http://backend:8000`（rewrites 写入）
- 容器运行期注入 `API_UPSTREAM_URL`、`API_BASE_URL`、`AUTH_SECRET`、`DATABASE_URL`
- GitHub Actions **Secrets**：`AUTH_SECRET`、`SENTRY_DSN`、`SENTRY_AUTH_TOKEN`
- GitHub Actions **Variables**：`SENTRY_ORG`、`SENTRY_PROJECT`（或 `SENTRY_APPLICATION_ID`）、`SENTRY_URL`
- 容器启动：`prisma migrate deploy && node server.js`

**不再部署** `frontend-ts` Nginx 容器；无需迁移 `frontend-ts/nginx.conf`。

## 错误监控（Better Stack）

运行时错误通过 Sentry 兼容 SDK 上报（`SENTRY_DSN`）。生产堆栈反解需要 **构建期** 上传 SourceMap：

1. 在 Better Stack **Errors → Applications → Advanced settings** 获取 `SENTRY_ORG`、`SENTRY_PROJECT`、`SENTRY_URL`。
2. 创建 **Telemetry API token** 作为 `SENTRY_AUTH_TOKEN`（勿提交仓库）。
3. 本地验证（在 `frontend-share/.env` 填入上述变量后）：

```bash
cd frontend-share
pnpm build   # 构建日志应出现 source map upload
pnpm start
```

4. 在浏览器触发一次测试错误，到 Better Stack Issues 确认堆栈显示 `src/...` 源码路径而非 `static/chunks/...` 混淆行号。

未配置 `SENTRY_AUTH_TOKEN` 时构建仍会成功，但跳过 SourceMap 上传（CI 默认行为）。

## 目录说明

| 路径 | 职责 |
| --- | --- |
| `src/app/studio/` | 创作台 Client SPA（页面、组件、hooks、lib） |
| `src/app/dialog/generate/route.ts` | SSE 流式代理 |
| `src/app/product_info/[...path]/route.ts` | 商品识别长超时代理 |
| `src/services/api.ts` | 浏览器 API + OpenAPI 类型 |
| `src/lib/sse/` | SSE 解析、续传、ingest |
| `src/middleware.ts` | 保护 `/studio`，登录重定向 |
| `next.config.mjs` | standalone、API rewrites |
| `prisma/` | 用户表迁移 |

## 迁移参考

Vite → Next 踩坑与知识点对照见飞书文档 [Nextjs 全栈框架 — 实战经验](https://my.feishu.cn/docx/KpTkdzKaXoAHl6x0dP5cGBa1n5c)。
