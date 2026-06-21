"""MCP 工具冒烟测试。"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from server.app import create_mcp
from server.settings import McpSettings


@pytest.fixture
def settings() -> McpSettings:
    return McpSettings(
        MCP_BEARER_TOKEN="test-bearer-token-min-16-chars",
        MCP_PORT=3101,
    )


@pytest.fixture
def mock_service():
    service = MagicMock()
    service.send_message = AsyncMock(return_value={"message_id": "om_1"})
    service.get_auth_status = AsyncMock(
        return_value={"bot": {"available": True}, "user": {"available": False}}
    )
    return service


def test_create_mcp_registers_seven_tools(settings: McpSettings) -> None:
    mcp = create_mcp(settings)
    tools = asyncio.run(mcp.list_tools())
    names = {tool.name for tool in tools}
    assert names == {
        "send_message",
        "reply_message",
        "list_chat_messages",
        "search_chats",
        "get_lark_auth_status",
        "notify_review_passed",
        "get_lark_setup_guide",
    }


def test_get_lark_auth_status_tool(settings: McpSettings, mock_service) -> None:
    async def _run():
        with patch(
            "server.app.get_lark_im_service_singleton",
            return_value=mock_service,
        ):
            mcp = create_mcp(settings)
            return await mcp.call_tool("get_lark_auth_status", {})

    result = asyncio.run(_run())
    assert result.content
    text = result.content[0].text
    assert "bot" in text
    mock_service.get_auth_status.assert_awaited_once()


def test_notify_review_passed_tool(settings: McpSettings, mock_service) -> None:
    mock_service.send_review_notification = AsyncMock(return_value={"message_id": "om_2"})

    async def _run():
        with patch(
            "server.app.get_lark_im_service_singleton",
            return_value=mock_service,
        ):
            mcp = create_mcp(settings)
            return await mcp.call_tool(
                "notify_review_passed",
                {"title": "标题", "content": "正文"},
            )

    result = asyncio.run(_run())
    text = result.content[0].text
    assert "message_id" in text
    mock_service.send_review_notification.assert_awaited_once()


def test_get_lark_setup_guide_tool(settings: McpSettings) -> None:
    mcp = create_mcp(settings)
    result = asyncio.run(mcp.call_tool("get_lark_setup_guide", {}))
    text = result.content[0].text
    assert "LARK_APP_ID" in text
    assert "INTEGRATION" in text or "env_vars" in text
