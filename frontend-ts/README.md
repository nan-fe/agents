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
│   ├── utils/
│   │   └── helper.ts              # 工具函数
│   └── types.ts                   # TypeScript类型定义
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
同时将 api.ts 里面的 API_PATH_URL 设置成 http://localhost:8080


前端应用将在 `http://localhost:3000` 运行。

## 构建生产版本

```bash
pnpm run build
```

构建结果将输出到 `build` 目录。

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