# 前端应用说明

## 项目结构

```
frontend/
├── public/              # 静态资源
│   └── index.html       # HTML入口文件
├── src/                 # 源代码
│   ├── App.js           # 主组件
│   ├── index.js         # 入口文件
│   ├── components/      # 组件
│   │   ├── InputForm.js     # 输入表单
│   │   ├── AgentLogs.js     # Agent日志
│   │   └── ResultDisplay.js # 结果展示
│   ├── services/        # 服务
│   │   └── api.js           # API服务
│   ├── styles/          # 样式
│   │   └── App.css          # 主样式文件
│   └── utils/           # 工具函数
│       └── helpers.js        # 辅助函数
├── package.json         # 前端依赖
└── README.md            # 前端说明
```

## 安装依赖

```bash
npm install
```

## 启动开发服务器

```bash
npm start
```

前端应用将在 `http://localhost:3000` 运行。

## 构建生产版本

```bash
npm run build
```

构建结果将输出到 `build` 目录。

## 功能说明

1. **输入表单**：用户输入内容描述，例如"推荐一款适合学生党的平价防晒霜，清爽不油腻"。
2. **Agent日志**：实时显示各Agent的思考过程，增加透明度和趣味性。
3. **结果展示**：展示最终生成的小红书风格文案和图片。

## 技术栈

- React 18
- React Markdown
- Server-Sent Events (SSE) 实时通信
