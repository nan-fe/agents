# Lark IM — 飞书即时通讯 SDK + MCP Server

独立仓库：提供 `lark_im` Python SDK 与 Streamable HTTP MCP 服务，供自研 Agent / Cursor 等 MCP Client 调用。

## 能力

- **SDK**（`lark_im`）：发消息、回复、搜群、读群消息、审核通过通知模板
- **MCP Server**（`server`）：HTTP MCP，`tools/list` + `tools/call`
- **个人账号**：未配置 `LARK_APP_ID` 时自动走本机 `lark-cli` 用户授权
- **企业应用**：配置 `LARK_APP_ID` + `LARK_APP_SECRET`，以 bot 身份调 OpenAPI

## 安装

```bash
pip install -e ".[mcp]"
cp .env.example .env   # 编辑 MCP_BEARER_TOKEN、LARK_NOTIFY_CHAT_ID 等
```

个人账号还需：

```bash
npm i -g @larksuite/lark-cli   # 或按官方文档安装
lark-cli config init
lark-cli auth login --scope "im:message im:message.send_as_user im:message:readonly"
```

## 启动 MCP Server

```bash
python -m server
# 或
lark-im-mcp
```

默认：`http://0.0.0.0:3101/mcp`，健康检查 `GET /health`。

## MCP Client 连接

任意 MCP Client（Cursor、自研 Agent、百炼）：

详见 **[对外接入手册](docs/INTEGRATION.md)** 与 [`docs/BAILEIAN_EXAMPLE.json`](docs/BAILEIAN_EXAMPLE.json)。

## 作为 Python SDK 使用（同进程）

```python
from lark_im import get_lark_im_service

service = get_lark_im_service()
await service.send_message("oc_xxx", markdown="## Hello")
```

## 在其他项目中依赖

```bash
pip install "lark-im @ git+https://github.com/you/lark-im-mcp.git"
```

或 monorepo：

```bash
pip install -e ../mcp-lark
```

环境变量与 `.env` 由 `lark_im` 包读取（包根目录或进程工作目录下的 `.env`）。

## Docker

```bash
docker build -t lark-im-mcp .
docker run --env-file .env -p 3101:3101 lark-im-mcp
```

注意：容器内使用 `lark-cli` 需自行挂载凭证；云上请用方案 3（`LARK_APP_ID` + `LARK_USE_CLI=false`）。

## 方案 3：个人账号用 lark-cli 同款应用 Bot 上云

你本机 `lark-cli config` 里的应用（如 `cli_aab9314aaf64dbb5`）可在云上作为 **机器人** 调 OpenAPI，无需 lark-cli 登录态。

### 1. 获取 App Secret

任选其一：

- 打开 [飞书开放平台](https://open.feishu.cn/app) → 找到该应用 → **凭证与基础信息** → 复制 App Secret
- 本机 Mac（lark-cli 已配置时）：

```bash
security find-generic-password -s "appsecret:cli_aab9314aaf64dbb5" -w
```

### 2. 开放平台权限

在应用 **权限管理** 中开通并发布：

- `im:message`（发消息）
- `im:message:readonly`（读消息、搜群）

### 3. 把机器人加进通知群

飞书群 → 群设置 → 添加成员 → 搜索 **应用名称**（非你的个人昵称）→ 添加。

未加群时 Bot 发消息会失败。

### 4. `.env` 配置

```env
LARK_APP_ID=cli_aab9314aaf64dbb5
LARK_APP_SECRET=你的Secret
LARK_DEFAULT_IDENTITY=bot
LARK_USE_CLI=false
LARK_NOTIFY_CHAT_ID=oc_xxx
MCP_BEARER_TOKEN=长随机串
```

### 5. 本地验证

```bash
pip install -e ".[mcp]"
# 填好 .env 后
python -c "
import asyncio
from lark_im import get_lark_im_service
async def main():
    s = get_lark_im_service()
    print(await s.get_auth_status())
asyncio.run(main())
"
```

`bot.available` 应为 `true`。再测发消息（替换 chat_id）：

```bash
python -c "
import asyncio
from lark_im import get_lark_im_service
async def main():
    await get_lark_im_service().send_message('oc_xxx', text='方案3 Bot 测试')
asyncio.run(main())
"
```

### 6. 部署到 Render / Fly

在平台 **Environment Variables** 填入与 `.env` 相同变量（不要提交 Git）。MCP URL：

`https://你的子域名.onrender.com/mcp`，`type: streamableHttp`。

## MCP Tools

| Tool | 说明 |
|------|------|
| `send_message` | 向群聊发 text/markdown |
| `reply_message` | 回复消息 |
| `list_chat_messages` | 拉取群消息 |
| `search_chats` | 搜群 |
| `get_lark_auth_status` | 检查 bot/user 凭证 |
| `notify_review_passed` | 发送审核通过通知（须用户确认） |
| `get_lark_setup_guide` | 接入配置引导 |

## 开发

```bash
pip install -e ".[mcp]"
pytest
```
