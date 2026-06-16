# 前端应用说明

## 项目结构

```
frontend-ts/
├── src/
│   ├── components/                # UI组件
│   │   ├── agent-logs.tsx         # Agent日志展示
│   │   └── result-display.tsx     # 结果展示组件
│   ├── pages/
│   │   └── dialog-content.tsx     # 对话页面
│   ├── services/
│   │   └── api.ts                 # API调用服务
│   ├── api/
│   │   └── schema.d.ts            # OpenAPI 生成的 API 类型
│   ├── utils/
│   │   └── helper.ts              # 工具函数
├── public/                        # 静态资源
├── package.json                   # 依赖配置
├── tailwind.config.js             # Tailwind配置
└── Dockerfile                     # Docker配置
```

## 安装依赖

```bash
pnpm install
```

## 启动开发服务器

```bash
pnpm run start
```
### 本地运行注意事项
需要将 nginx 文件注释
如需覆盖后端地址，可在环境变量中设置 `VITE_API_BASE_URL`，默认开发环境为 `http://localhost:8000`
如需覆盖前端错误监控 DSN，可设置 `VITE_SENTRY_DSN`（默认使用 Better Stack DSN）


前端应用将在 `http://localhost:5173` 运行。

## API 类型 SSOT

前端 API 类型以后端 FastAPI 的 OpenAPI schema 为唯一事实源，不再维护手写 `types.ts`。

生成步骤：

```bash
# 先确保后端已启动，并能访问 http://localhost:8000/openapi.json
pnpm run gen:api
```

生成文件为 `src/api/schema.d.ts`，由 `openapi-typescript` 维护，不要手动修改。业务代码通过 `components["schemas"]` 派生类型：

```ts
import type { components } from "../api/schema";

export type UserInput = components["schemas"]["UserInput"];
```

后端请求模型或路由变更后，需要重新执行 `pnpm run gen:api`，再运行前端类型检查或构建验证。

## 构建生产版本

```bash
pnpm run build
```

构建结果将输出到 `dist` 目录。

## 功能说明

1. **输入表单**：用户输入内容描述，例如"推荐一款适合学生党的平价防晒霜，清爽不油腻"。
2. **Agent日志**：实时显示各Agent的思考过程，增加透明度和趣味性。
3. **结果展示**：展示最终生成的小红书风格文案和图片。

## 技术栈

- React 19
- React Markdown
- Server-Sent Events (SSE) 实时通信
- tailwind

## 基建能力

- 支持 eslint/prettierrc，可以通过手动运行 npx eslint src/ --fix 进行修复
- 支持 docker 部署，github PR 会自动触发 docker self host 部署