"""商品信息爬虫 MCP Server — Streamable HTTP + Bearer Token。"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from server.auth import build_static_bearer_auth
from server.bootstrap import get_product_info_service, init_product_stack
from server.settings import McpSettings, load_settings

MCP_INSTRUCTIONS = """你是电商选品池助手。支持淘宝、天猫、京东商品链接（含 e.tb.cn 等短链）。

入库流程（默认）：
1. 调用 scrape_product_preview，传入商品 URL，获取结构化预览与 preview_token。
2. 向用户展示预览（名称、价格、店铺、摘要、评论摘要），询问是否加入选品池。
3. 用户确认后，调用 confirm_product_preview，传入 preview_token 完成入库。

其他工具：
- list_products / get_product / delete_product：管理选品池。
- scrape_and_save_product：跳过确认直接入库，仅在用户明确要求时使用。

所有写操作会同步更新 RAG 检索索引。"""


def _json_text(payload: Any) -> str:
    if hasattr(payload, "model_dump"):
        payload = payload.model_dump()
    return json.dumps(payload, ensure_ascii=False, indent=2)


def create_mcp(settings: McpSettings) -> FastMCP:
    auth = build_static_bearer_auth(settings.MCP_BEARER_TOKEN)

    mcp = FastMCP(
        name="product-scraper",
        version="0.1.0",
        instructions=MCP_INSTRUCTIONS,
        auth=auth,
    )

    @mcp.custom_route("/health", methods=["GET"])
    async def health(_request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "service": "product-scraper-mcp"})

    @mcp.tool(
        name="scrape_product_preview",
        description=(
            "识别淘宝/天猫/京东商品链接并返回预览（不入库）。"
            "返回 preview_token，用户确认后需调用 confirm_product_preview。"
        ),
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "openWorldHint": True,
        },
    )
    async def scrape_product_preview(url: str) -> str:
        service = get_product_info_service()
        try:
            result = await service.preview_from_url(url)
        except ValueError as exc:
            return _json_text({"error": str(exc)})
        return _json_text(result)

    @mcp.tool(
        name="confirm_product_preview",
        description=(
            "将 scrape_product_preview 返回的 preview_token 对应商品写入选品池并更新 RAG 索引。"
            "仅在用户明确确认入库后调用。"
        ),
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "openWorldHint": False,
        },
    )
    async def confirm_product_preview(preview_token: str) -> str:
        service = get_product_info_service()
        try:
            result = await service.confirm_preview(preview_token)
        except ValueError as exc:
            return _json_text({"error": str(exc)})
        return _json_text(result)

    @mcp.tool(
        name="scrape_and_save_product",
        description=(
            "从商品 URL 抓取信息并直接加入选品池（跳过预览确认）。"
            "默认应使用 scrape_product_preview + confirm_product_preview。"
        ),
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "openWorldHint": True,
        },
    )
    async def scrape_and_save_product(url: str) -> str:
        service = get_product_info_service()
        try:
            result = await service.create_from_url(url)
        except ValueError as exc:
            return _json_text({"error": str(exc)})
        return _json_text(result)

    @mcp.tool(
        name="list_products",
        description="列出选品池中全部商品（按 id 倒序）。",
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "openWorldHint": False,
        },
    )
    async def list_products() -> str:
        service = get_product_info_service()
        return _json_text(service.list_products())

    @mcp.tool(
        name="get_product",
        description="按 product_id 获取选品池商品详情（含头图 URL 与评论摘要）。",
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "openWorldHint": False,
        },
    )
    async def get_product(product_id: str) -> str:
        service = get_product_info_service()
        product = service.get_product(product_id)
        if not product:
            return _json_text({"error": f"商品不存在: {product_id}"})
        return _json_text(product)

    @mcp.tool(
        name="delete_product",
        description="从选品池删除商品，并同步移除 RAG 索引与爬虫记录。",
        annotations={
            "readOnlyHint": False,
            "destructiveHint": True,
            "openWorldHint": False,
        },
    )
    async def delete_product(product_id: str) -> str:
        service = get_product_info_service()
        if not service.delete_product(product_id):
            return _json_text({"error": f"商品不存在: {product_id}"})
        return _json_text({"ok": True, "product_id": product_id})

    return mcp


def run_server() -> None:
    settings = load_settings()
    asyncio.run(init_product_stack(settings))
    mcp = create_mcp(settings)
    mcp.run(
        transport="http",
        host=settings.MCP_HOST,
        port=settings.MCP_PORT,
        path=settings.MCP_PATH,
    )
