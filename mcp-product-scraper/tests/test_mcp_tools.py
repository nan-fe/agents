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
        MCP_PORT=3100,
        MCP_WARM_RAG_ON_START=False,
    )


@pytest.fixture
def mock_service():
    service = MagicMock()
    service.preview_from_url = AsyncMock(
        return_value=MagicMock(
            model_dump=lambda: {
                "preview_token": "tok_abc",
                "product": {"id": "0", "name": "测试商品"},
                "message": "ok",
            }
        )
    )
    service.list_products = MagicMock(
        return_value=MagicMock(model_dump=lambda: {"items": [], "total": 0})
    )
    return service


def test_create_mcp_registers_six_tools(settings: McpSettings) -> None:
    mcp = create_mcp(settings)
    tools = asyncio.run(mcp.list_tools())
    names = {tool.name for tool in tools}
    assert names == {
        "scrape_product_preview",
        "confirm_product_preview",
        "scrape_and_save_product",
        "list_products",
        "get_product",
        "delete_product",
    }


def test_list_products_tool(settings: McpSettings, mock_service) -> None:
    async def _run():
        with patch(
            "server.app.get_product_info_service",
            return_value=mock_service,
        ):
            mcp = create_mcp(settings)
            return await mcp.call_tool("list_products", {})

    result = asyncio.run(_run())
    assert result.content
    text = result.content[0].text
    assert "items" in text
    mock_service.list_products.assert_called_once()
