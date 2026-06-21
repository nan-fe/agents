"""初始化 backend 依赖与 ProductInfoService 单例。"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from server.settings import McpSettings

_rag_agent = None
_service = None
_init_lock: asyncio.Lock | None = None


def _load_backend_env(backend_dir: Path) -> None:
    env_path = backend_dir / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)


def _ensure_backend_on_path(backend_dir: Path) -> None:
    backend_str = str(backend_dir.resolve())
    if backend_str not in sys.path:
        sys.path.insert(0, backend_str)


def _ensure_chroma_db_path(settings: McpSettings) -> None:
    if not os.environ.get("CHROMA_DB_PATH"):
        os.environ["CHROMA_DB_PATH"] = settings.chroma_db_path


def get_product_info_service():
    if _service is None:
        raise RuntimeError(
            "ProductInfoService 尚未初始化，请先调用 init_product_stack"
        )
    return _service


async def init_product_stack(settings: McpSettings) -> None:
    global _rag_agent, _service, _init_lock

    if _init_lock is None:
        _init_lock = asyncio.Lock()

    async with _init_lock:
        if _service is not None:
            return

        _ensure_backend_on_path(settings.backend_dir)
        _load_backend_env(settings.backend_dir)
        _ensure_chroma_db_path(settings)

        from app.agents.product_rag_system.agent import ProductRagAgent
        from app.services.product_info_service import ProductInfoService

        csv_path = settings.products_csv_path
        _rag_agent = ProductRagAgent(data_path=csv_path)
        _service = ProductInfoService(_rag_agent)

        if settings.MCP_WARM_RAG_ON_START:
            try:
                await _rag_agent.ensure_index_ready()
            except Exception as exc:
                print(
                    "[mcp-product-scraper] RAG 索引预热失败（首次入库时会重试）: "
                    f"{exc}"
                )
