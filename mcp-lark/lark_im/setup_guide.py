"""飞书接入引导（不含 Secret）。"""

from __future__ import annotations

from typing import Any


def get_lark_setup_guide_payload() -> dict[str, Any]:
    return {
        "scheme": "bot_openapi",
        "description": "使用飞书开放平台应用机器人（方案 3），云上无需 lark-cli。",
        "steps": [
            {
                "title": "获取应用凭证",
                "detail": "飞书开放平台 → 应用 → 凭证与基础信息 → 复制 App ID 与 App Secret。",
                "url": "https://open.feishu.cn/app",
            },
            {
                "title": "开通并发布权限",
                "detail": "权限管理：im:message、im:message:readonly，提交发布。",
            },
            {
                "title": "机器人进群",
                "detail": "在目标群添加成员 → 搜索应用名称（非个人昵称）→ 添加。",
            },
            {
                "title": "配置服务器环境变量",
                "detail": "写入 backend/.env 或 mcp-lark/.env，勿提交 Git。",
            },
            {
                "title": "（可选）部署 MCP HTTP",
                "detail": "百炼/Cursor 调工具需单独部署 mcp-lark :3101，创作台自动通知仅需 backend 内嵌 SDK。",
            },
        ],
        "env_vars": [
            {"name": "LARK_APP_ID", "required": True, "example": "cli_xxx"},
            {"name": "LARK_APP_SECRET", "required": True, "secret": True},
            {"name": "LARK_DEFAULT_IDENTITY", "required": True, "example": "bot"},
            {"name": "LARK_USE_CLI", "required": False, "example": "false"},
            {"name": "LARK_NOTIFY_CHAT_ID", "required": True, "example": "oc_xxx"},
            {"name": "LARK_NOTIFY_ENABLED", "required": False, "example": "true"},
            {"name": "LARK_NOTIFY_MODE", "required": False, "example": "auto|prompt|off"},
            {"name": "MCP_BEARER_TOKEN", "required": False, "note": "仅 MCP HTTP Server"},
        ],
        "mcp_client_example": {
            "url": "http://127.0.0.1:3101/mcp",
            "type": "streamableHttp",
            "headers": {"Authorization": "Bearer <MCP_BEARER_TOKEN>"},
        },
        "docs": "mcp-lark/docs/INTEGRATION.md",
        "authorization": {
            "layers": [
                {
                    "name": "mcp_bearer",
                    "credential": "MCP_BEARER_TOKEN",
                    "where": "mcp-lark/.env + Client headers.Authorization",
                    "required_for": "百炼/Cursor 调 MCP 工具",
                },
                {
                    "name": "feishu_openapi",
                    "credential": "LARK_APP_ID + LARK_APP_SECRET → tenant_access_token",
                    "where": "backend/.env 或 mcp-lark/.env",
                    "required_for": "发消息、审核通知、search_chats 等",
                },
            ],
            "bot_flow": [
                "开放平台获取 App ID / Secret",
                "开通 im:message、im:message:readonly 并发布版本",
                "机器人加入目标群",
                "配置 LARK_NOTIFY_CHAT_ID",
                "get_lark_auth_status 验证 bot.available",
            ],
            "verify_tools": ["get_lark_auth_status", "GET /lark/status"],
            "oauth": {
                "authorize": "GET /lark/oauth/authorize",
                "callback": "GET /lark/oauth/callback",
                "register": "POST /lark/oauth/register",
                "user_status": "GET /lark/oauth/user",
            },
            "docs_section": "INTEGRATION.md#授权体系",
        },
    }
