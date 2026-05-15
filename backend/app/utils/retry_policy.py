"""
HTTP / LLM 调用策略化重试：仅对幂等、可恢复错误重试；4xx（除 429）不重试。
指数退避 + 抖动，减轻惊群。

编排层若需「LLM 驱动重试决策」（OrchestratorLLMService.retry_prompt），
应先用本模块的 is_transient_exception 做门控，避免无意义的全链路重跑与双倍成本。
"""
from __future__ import annotations

import asyncio
import logging
import random
from typing import Awaitable, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

try:
    import httpx
except ImportError:  # pragma: no cover
    httpx = None

try:
    from openai import (
        APIConnectionError,
        APIError,
        APITimeoutError,
        AuthenticationError,
        BadRequestError,
        PermissionDeniedError,
        RateLimitError,
    )
except ImportError:  # pragma: no cover

    class _Missing:
        pass

    APIConnectionError = APITimeoutError = RateLimitError = _Missing  # type: ignore
    APIError = AuthenticationError = BadRequestError = PermissionDeniedError = _Missing  # type: ignore


def _unwrap_cause(exc: BaseException) -> BaseException:
    seen: set[int] = set()
    cur: BaseException | None = exc
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        nxt = cur.__cause__ if cur.__cause__ is not None else None
        if nxt is None:
            break
        cur = nxt
    return cur or exc


def is_transient_exception(exc: BaseException) -> bool:
    """是否适合对同一请求做有限次重试（幂等读类 / 生成类在业务上可接受时）。"""
    root = _unwrap_cause(exc)

    if isinstance(root, (asyncio.TimeoutError, TimeoutError)):
        return True

    if isinstance(root, RateLimitError):
        return True
    if isinstance(root, APIConnectionError):
        return True
    if isinstance(root, APITimeoutError):
        return True

    if isinstance(root, BadRequestError):
        return False
    if isinstance(root, AuthenticationError):
        return False
    if isinstance(root, PermissionDeniedError):
        return False

    if isinstance(root, APIError):
        code = getattr(root, "status_code", None)
        if code is None:
            return False
        if code == 429:
            return True
        if code in (500, 502, 503, 504):
            return True
        if 400 <= code < 500:
            return False

    if httpx is not None:
        if isinstance(root, (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout)):
            return True
        if isinstance(root, httpx.HTTPStatusError):
            c = root.response.status_code
            if c == 429 or c >= 500:
                return True
            return False

    if isinstance(root, (ConnectionError, OSError)):
        return True

    return False


def classify_agent_failure(exc: BaseException) -> str:
    """供编排层 / 前端展示的稳定错误码。"""
    root = _unwrap_cause(exc)
    if isinstance(root, (asyncio.TimeoutError, TimeoutError)):
        return "TIMEOUT"
    if isinstance(root, RateLimitError):
        return "RATE_LIMIT"
    if isinstance(root, APIError):
        code = getattr(root, "status_code", None)
        if code == 429:
            return "RATE_LIMIT"
        if code in (500, 502, 503, 504):
            return "UPSTREAM_5XX"
        if code is not None and 400 <= code < 500:
            return "CLIENT_4XX"
    if isinstance(root, ValueError):
        return "VALIDATION"
    return "UNKNOWN"


async def retry_with_backoff(
    factory: Callable[[], Awaitable[T]],
    *,
    max_attempts: int,
    base_delay: float,
    max_delay: float,
    operation_name: str = "async_call",
    is_retryable: Callable[[BaseException], bool] = is_transient_exception,
) -> T:
    """对 factory 返回的协程做有限次重试；退避带抖动。"""
    last: BaseException | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return await factory()
        except BaseException as e:
            last = e
            if attempt >= max_attempts or not is_retryable(e):
                raise
            delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
            delay *= 0.75 + random.random() * 0.5
            logger.warning(
                "%s 第 %s/%s 次失败: %s，%.2fs 后重试",
                operation_name,
                attempt,
                max_attempts,
                e,
                delay,
            )
            await asyncio.sleep(delay)
    assert last is not None
    raise last
