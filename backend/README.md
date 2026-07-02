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

微博自动发布**默认只需 Playwright**（已包含在 `requirements.txt`）。`browser-use` 为可选兜底，**不要**写进主依赖：

```bash
# 若 Playwright 发布失败，需要 LLM 兜底时再装（Python 3.11+，建议官方 PyPI）：
pip install -r requirements-social.txt -i https://pypi.org/simple

# 若仍报 No matching distribution found for browser-use[core]：
pip install "browser-use>=0.12.0" -i https://pypi.org/simple
```

安装 Playwright 浏览器：

```bash
python -m playwright install chromium
```

### 微博 / X 自动发布（可选）

在 `.env` 中配置（详见 `.env.example`）：

- `WEIBO_PUBLISH_ENABLED=true` — 启用微博发布
- `WEIBO_PUBLISH_AUTO_ON_COMPLETE=true` — **内容生成且审核通过后自动发微博**（默认开启）
- `WEIBO_PUBLISH_ENGINE=browser_use` — 使用 browser-use Agent 打开微博并发布（推荐）
- `BROWSER_USE_PROFILE_PATH` — 浏览器 Profile 目录（路径名勿含 `chrome`）
- `WEIBO_PUBLISH_DRY_RUN=true` — 本地演练，不真发

**本地登录 → 线上自动发布：**

1. 本地登录（macOS `open` 打开 Playwright Chromium，写入 `data/weibo-profile`）：

   ```bash
   bash scripts/weibo-login.sh
   ```

   在弹出的浏览器里完成微博登录，**关闭浏览器**后再同步。

2. 同步 Profile 到服务器（Docker 挂载 `/data/weibo-profile` 后自动复用 Cookie）：

   ```bash
   bash scripts/sync-weibo-profile.sh root@your-server
   ```

3. 验证：`GET http://localhost:8000/social/status`（`weibo.logged_in` 应为 `true`）

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
