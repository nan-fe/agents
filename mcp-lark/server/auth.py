"""Bearer Token 鉴权（FastMCP StaticTokenVerifier）。"""

from __future__ import annotations

from fastmcp.server.auth.providers.jwt import StaticTokenVerifier


def build_static_bearer_auth(token: str) -> StaticTokenVerifier:
    return StaticTokenVerifier(
        tokens={
            token: {
                "client_id": "mcp-lark",
                "scopes": ["lark:read", "lark:write"],
            }
        }
    )
