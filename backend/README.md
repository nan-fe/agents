# 后端服务说明

## 项目结构

```
backend/
├── app/                 # 应用代码
│   ├── __init__.py
│   ├── main.py          # FastAPI 应用入口
│   ├── config.py        # 配置管理
│   ├── models/          # 数据模型
│   ├── agents/          # 多Agent核心模块
│   ├── services/        # 外部服务与工具
│   └── utils/           # 工具函数
├── tests/               # 测试文件
├── .env                 # 环境变量
├── requirements.txt     # Python依赖
└── README.md            # 后端说明
```

## 安装依赖

```bash
pip install -r requirements.txt
```

## 配置环境变量

在 `.env` 文件中设置以下环境变量：

- `OPENAI_API_KEY`: OpenAI API 密钥
- `OPENAI_MODEL`: OpenAI 模型名称（默认：gpt-4）
- `IMAGE_MODEL`: 图片生成模型（默认：dall-e-3）
- `REPLICATE_API_KEY`: Replicate API 密钥（使用 Stable Diffusion 时需要）

## 启动服务

```bash
uvicorn app.main:app --reload
```

服务将在 `http://localhost:8000` 运行。

## API 端点

- `POST /generate`: 生成小红书内容
  - 请求体：`{"prompt": "推荐一款适合学生党的平价防晒霜，清爽不油腻"}`
  - 响应：Server-Sent Events (SSE) 流式输出

## 测试

```bash
pytest tests/
```
