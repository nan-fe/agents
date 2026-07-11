"""X OAuth API 专用 HTTP 客户端（不用于 Web 发帖）。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx

from app.config import settings


def x_api_client_kwargs(*, timeout: float = 30.0) -> dict:
    kwargs: dict = {"timeout": timeout, "trust_env": False}
    proxy = (settings.X_HTTP_PROXY or "").strip()
    if proxy:
        kwargs["proxy"] = proxy
    return kwargs


@asynccontextmanager
async def x_api_client(*, timeout: float = 30.0) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(**x_api_client_kwargs(timeout=timeout)) as client:
        yield client
