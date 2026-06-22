"""飞书 IM MCP Server — Streamable HTTP + Bearer Token。"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Literal

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from lark_im.setup_guide import get_lark_setup_guide_payload
from server.auth import build_static_bearer_auth
from server.bootstrap import get_lark_im_service_singleton, init_lark_stack
from server.settings import McpSettings, load_settings

MCP_INSTRUCTIONS = """你是飞书即时通讯助手。支持向群聊发消息、回复、搜索群、读取群消息，以及审核通过后的飞书推送。

安全约束（必须遵守）：
- 调用 send_message / reply_message / notify_review_passed 前，必须向用户确认收件人与内容。
- 不要未经用户明确同意发送消息。

个人账号（无企业自建应用）：
- 在本机安装并登录 lark-cli（config init + auth login），未配置 LARK_APP_ID 时自动通过 lark-cli 以用户身份发消息。
- 用 search_chats 查群名获取 chat_id，将 LARK_NOTIFY_CHAT_ID 写入 backend/.env。

工具说明：
- send_message：向 chat_id 发送 text 或 markdown 消息。
- reply_message：回复指定 message_id。
- list_chat_messages：读取群最近消息。
- search_chats：按名称搜索群。
- get_lark_auth_status：检查 bot/user 凭证是否可用。
- notify_review_passed：发送审核通过通知到配置的通知群（仅用户明确确认后调用）。
- get_lark_setup_guide：返回飞书开放平台配置步骤（不含 Secret）。

Reviewer 审核通过后的工作流：
1. 检测生成结果中的 review_approved 与 lark_notification 元数据。
2. 若 eligible 且未 auto_sent，向用户展示 prompt 并询问是否推送到飞书。
3. 调用 get_lark_auth_status，确认 bot.available 为 true。
4. 用户确认后调用 notify_review_passed（参数与生成结果字段对齐）。

创作台 backend 在 LARK_NOTIFY_MODE=auto 时会自动推送；MCP 用于百炼等外部 Agent 按需触发。"""


def _json_text(payload: Any) -> str:
    if hasattr(payload, "model_dump"):
        payload = payload.model_dump()
    return json.dumps(payload, ensure_ascii=False, indent=2)


def create_mcp(settings: McpSettings) -> FastMCP:
    auth = build_static_bearer_auth(settings.MCP_BEARER_TOKEN)

    mcp = FastMCP(
        name="lark-im",
        version="0.1.0",
        instructions=MCP_INSTRUCTIONS,
        auth=auth,
    )

    @mcp.custom_route("/health", methods=["GET"])
    async def health(_request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "service": "lark-im-mcp"})

    @mcp.tool(
        name="send_message",
        description=(
            "向飞书群聊发送消息。需提供 chat_id，以及 text 或 markdown 之一。"
            "identity 可选 bot（默认）或 user。发送前须与用户确认收件人与内容。"
        ),
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "openWorldHint": True,
        },
    )
    async def send_message(
        chat_id: str,
        text: str | None = None,
        markdown: str | None = None,
        identity: Literal["bot", "user"] | None = None,
    ) -> str:
        service = get_lark_im_service_singleton()
        try:
            result = await service.send_message(
                chat_id,
                text=text,
                markdown=markdown,
                identity=identity,
            )
        except ValueError as exc:
            return _json_text({"error": str(exc)})
        return _json_text(result)

    @mcp.tool(
        name="reply_message",
        description=(
            "回复飞书消息。需提供 message_id 与 text 或 markdown。发送前须与用户确认内容与身份。"
        ),
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "openWorldHint": False,
        },
    )
    async def reply_message(
        message_id: str,
        text: str | None = None,
        markdown: str | None = None,
        identity: Literal["bot", "user"] | None = None,
    ) -> str:
        service = get_lark_im_service_singleton()
        try:
            result = await service.reply_message(
                message_id,
                text=text,
                markdown=markdown,
                identity=identity,
            )
        except ValueError as exc:
            return _json_text({"error": str(exc)})
        return _json_text(result)

    @mcp.tool(
        name="list_chat_messages",
        description="拉取指定群聊的最近消息（container_id 为 chat_id）。",
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "openWorldHint": False,
        },
    )
    async def list_chat_messages(
        chat_id: str,
        page_size: int = 20,
        identity: Literal["bot", "user"] | None = None,
    ) -> str:
        service = get_lark_im_service_singleton()
        try:
            result = await service.list_chat_messages(
                chat_id,
                page_size=page_size,
                identity=identity,
            )
        except ValueError as exc:
            return _json_text({"error": str(exc)})
        return _json_text(result)

    @mcp.tool(
        name="search_chats",
        description="按名称关键词搜索飞书群聊。",
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "openWorldHint": True,
        },
    )
    async def search_chats(
        query: str,
        page_size: int = 20,
        identity: Literal["bot", "user"] | None = None,
    ) -> str:
        service = get_lark_im_service_singleton()
        try:
            result = await service.search_chats(
                query,
                page_size=page_size,
                identity=identity,
            )
        except ValueError as exc:
            return _json_text({"error": str(exc)})
        return _json_text(result)

    @mcp.tool(
        name="get_lark_auth_status",
        description="检查飞书 bot（app_id/secret）与 user（access_token）凭证是否可用。",
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "openWorldHint": False,
        },
    )
    async def get_lark_auth_status() -> str:
        service = get_lark_im_service_singleton()
        return _json_text(await service.get_auth_status())

    @mcp.tool(
        name="notify_review_passed",
        description=(
            "将审核通过的内容推送到 LARK_NOTIFY_CHAT_ID 配置的飞书群。"
            "参数与生成结果字段对齐。仅当用户明确确认推送后调用；"
            "调用前建议先 get_lark_auth_status 确认 bot.available。"
        ),
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "openWorldHint": True,
        },
    )
    async def notify_review_passed(
        title: str,
        content: str,
        project_id: str | None = None,
        version: str | None = None,
        version_id: str | None = None,
        image_url: str | None = None,
        review_feedback: str | None = None,
    ) -> str:
        service = get_lark_im_service_singleton()
        result_dict: dict[str, Any] = {
            "title": title,
            "content": content,
        }
        if project_id:
            result_dict["project_id"] = project_id
        if version:
            result_dict["version"] = version
        if version_id:
            result_dict["version_id"] = version_id
        if image_url:
            result_dict["image_url"] = image_url
        if review_feedback:
            result_dict["review_feedback"] = review_feedback
        try:
            data = await service.send_review_notification(result_dict)
        except ValueError as exc:
            return _json_text({"error": str(exc)})
        return _json_text(data)

    @mcp.tool(
        name="get_lark_setup_guide",
        description=(
            "返回飞书开放平台接入步骤、权限 scope、环境变量清单与 MCP URL 示例（不含 Secret）。"
        ),
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "openWorldHint": False,
        },
    )
    async def get_lark_setup_guide() -> str:
        return _json_text(get_lark_setup_guide_payload())

    return mcp


def run_server() -> None:
    settings = load_settings()

    asyncio.run(init_lark_stack())
    mcp = create_mcp(settings)
    mcp.run(
        transport="http",
        host=settings.MCP_HOST,
        port=settings.MCP_PORT,
        path=settings.MCP_PATH,
    )
