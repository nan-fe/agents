# Frontend Share

`frontend-share` 是 XHS Multi-Agent Creator 的公开分享页应用。创作端生成内容后，会调用后端 `/shares` 保存一份快照，并生成 `/share/[shareId]` 链接；分享页根据 `shareId` 读取后端快照并展示标题、正文、标签和图片。

## 功能

- 公开访问 `/share/[shareId]` 展示已生成的小红书图文内容
- 生成 Open Graph / Twitter metadata，便于社交平台预览
- 支持复制分享链接、复制文案、分享到 X 和微博
- 对不存在的分享 ID 展示 404 页面，对加载错误展示错误页

## 技术栈

- Next.js App Router
- React
- TypeScript
- Tailwind CSS

## 本地开发

```bash
cd frontend-share
pnpm install
pnpm dev
```

默认访问地址：

- 分享页首页：`http://localhost:3000`
- 分享详情：`http://localhost:3000/share/[shareId]`

本地默认会请求 `http://localhost:8000` 作为后端 API。

## 环境变量

| 变量 | 说明 | 默认值 |
| --- | --- | --- |
| `API_BASE_URL` | 服务端渲染时请求后端 `/shares/{shareId}` 的地址，生产环境推荐配置 | `http://localhost:8000` |
| `NEXT_PUBLIC_API_BASE_URL` | 浏览器可见的后端 API 地址，未配置 `API_BASE_URL` 时作为回退 | `http://localhost:8000` |

示例：

```bash
API_BASE_URL=https://api.example.com pnpm build
API_BASE_URL=https://api.example.com pnpm start
```

## 与主创作端的关系

主创作端 `frontend-ts` 使用 `VITE_SHARE_BASE_URL` 拼出公开分享链接：

```env
VITE_SHARE_BASE_URL=https://share.example.com
```

后端提供分享快照接口：

- `POST /shares`：保存生成结果快照
- `GET /shares/{share_id}`：读取公开分享快照

后端默认将分享快照写入 `backend/app/data/shares.json`，可通过 `SHARE_STORE_PATH` 调整持久化路径。生产环境部署时应把该文件所在目录挂载为持久化卷，避免容器重启或重新部署后分享链接失效。

## 构建与部署

```bash
cd frontend-share
pnpm install
pnpm build
pnpm start
```

`next.config.mjs` 已开启 `output: 'standalone'`，适合容器化部署。生产部署时需要确保：

- `API_BASE_URL` 指向可被分享页服务端访问的后端地址
- 后端允许分享页域名跨域访问 `/shares/{share_id}`
- 主创作端配置 `VITE_SHARE_BASE_URL` 指向分享页公开域名
- 后端 `SHARE_STORE_PATH` 或默认数据目录具备持久化能力

项目已提供 `frontend-share/Dockerfile`，并接入根目录 `docker-compose.yml` 与 `.github/workflows/deploy.yml`：

- 镜像标签：`agents:frontend-share`
- Compose 服务名：`frontend-share`
- 容器端口：`3000`
- 默认宿主机端口：`3001`
- Compose 内部后端地址：`API_BASE_URL=http://backend:8000`

通过现有部署命令即可拉起分享页服务：

```bash
docker compose pull
docker compose up -d
```
