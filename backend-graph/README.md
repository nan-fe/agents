# XHS Multi-Agent Creator Backend with LangGraph

这是使用 LangGraph 重构的小红书多Agent创作系统后端。

## 功能特点

- 使用 LangGraph 构建多Agent协作流程
- 支持文案生成、图片生成、内容审核等功能
- 提供与原 backend 一致的 API 接口
- 支持流式输出（SSE）

## 目录结构

```
backend-graph/
├── app/
│   ├── agents/          # Agent 实现
│   ├── models/          # 数据模型
│   ├── services/        # 服务实现
│   ├── utils/           # 工具函数
│   ├── config.py        # 配置文件
│   ├── graph.py         # LangGraph 工作流
│   └── main.py          # FastAPI 应用
├── .env                 # 环境变量
├── requirements.txt     # 依赖包
└── README.md            # 说明文档
```

## 安装依赖

```bash
pip3 install -r requirements.txt
```

## 运行项目

```bash
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

## API 接口

### 1. 生成小红书内容

**POST /generate**

请求体：
```json
{
  "prompt": "生成一篇关于护肤的小红书内容"
}
```

响应：
- 流式输出（SSE），包含日志和最终结果

### 2. 对话式生成小红书内容

**POST /dialog/generate**

请求体：
```json
{
  "prompt": "修改一下内容，更加活泼可爱",
  "session_id": "session_123"
}
```

响应：
- 流式输出（SSE），包含日志和最终结果

### 3. 根路径

**GET /**

响应：
```json
{
  "message": "XHS Multi-Agent Creator API",
  "version": "1.0.0"
}
```

## 技术栈

- FastAPI：Web 框架
- LangGraph：Agent 协作框架
- LangChain：LLM 工具链
- OpenAI API：语言模型
- ChromaDB：会话历史存储
