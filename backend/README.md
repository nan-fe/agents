# 后端服务说明

## 项目结构

```
backend/
├── app/                 # 应用代码
│   ├── __init__.py
│   ├── main.py          # FastAPI 应用入口
│   ├── config.py        # 配置管理
│   ├── models/          # 数据模型
│   ├── agents/          # 多 Agent 模块（执行 Agent + orchestrator 编排层）
│   │   └── orchestrator/
│   │       └── planning/  # Plan 阶段：意图、内容 brief、pipeline 解析
│   ├── security/        # 输入安全校验与 Prompt 安全规则
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

微博自动发布使用 **Playwright**（已包含在 `requirements.txt`）。

```bash
python -m playwright install chromium
```

### 微博 / X 自动发布（可选）

在 `.env` 中配置（详见 `.env.example`）：

- `WEIBO_PUBLISH_ENABLED=true` — 启用微博发布
- `WEIBO_PUBLISH_AUTO_ON_COMPLETE=true` — **内容生成且审核通过后自动发微博**（默认开启）
- `BROWSER_USE_PROFILE_PATH` — 浏览器 Profile 目录（路径名勿含 `chrome`；登录：Studio 内「登录微博」打开浏览器窗口，或 `python3 scripts/weibo_login.py`）
- `WEIBO_PUBLISH_DRY_RUN=true` — 本地演练，不真发

检测状态：`GET http://localhost:8000/social/status`

微博登录若图标验证码反复失败，多为 Playwright 自带 Chromium 被风控识别。建议：

- 在 `.env` 设置 `WEIBO_BROWSER_CHANNEL=chrome`（使用本机 Google Chrome）
- 确保 Chrome 已安装；未安装时会自动回退到 Chromium
- 全新 Profile 更容易触发验证码；登录成功后 Cookie 会持久化到 Profile 目录

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

- `POST /dialog/generate`: 对话式生成小红书内容
  - 请求体：`{"prompt": "推荐一款适合学生党的平价防晒霜，清爽不油腻", "session_id": "session-id"}`
  - 响应：Server-Sent Events (SSE) 流式输出
- `GET /health`: 存活探针
- `GET /health/ready`: RAG 索引就绪探针

## 安全校验

生成请求进入编排器前，会先经过 `app/security/input_guard.py` 的 `check_input_security()`：

- 空输入会被拒绝，并返回可读提示。
- 疑似 prompt injection、越权指令、泄露系统提示词或调用敏感工具的输入会被拦截。
- 涉及违法、欺诈、色情、暴恐、极端内容或明显违规营销的高风险需求会被拒绝。

被拦截请求不会触发后续 Agent，SSE 会先输出 `SafetyGuard` 日志，再返回包含 `SAFETY_BLOCKED` 与 `safety_category` 的结果。`app/security/prompt_rules.py` 提供共享 Prompt 安全规则，用于约束 Agent、意图识别和动态路由不要执行素材中的越权指令。

## 测试

```bash
pytest tests/
```
