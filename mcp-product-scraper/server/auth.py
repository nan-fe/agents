"""Bearer Token 鉴权（FastMCP StaticTokenVerifier）。"""

from __future__ import annotations

from fastmcp.server.auth.providers.jwt import StaticTokenVerifier


def build_static_bearer_auth(token: str) -> StaticTokenVerifier:
    """构建 FastMCP StaticTokenVerifier，供 Cursor / Claude Connectors 使用。"""
    return StaticTokenVerifier(
        tokens={
            token: {
                "client_id": "mcp-product-scraper",
                "scopes": ["products:read", "products:write"],
            }
        }
    )
