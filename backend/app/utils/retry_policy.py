"""
HTTP / LLM 调用策略化重试：仅对幂等、可恢复错误重试；4xx（除 429）不重试。
指数退避 + 抖动，减轻惊群。

编排层重试 Agent 前，应先用本模块的 is_transient_exception 做门控，
避免无意义的全链路重跑与双倍成本。
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
        if isinstance(
            root, (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout)
        ):
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
    if isinstance(root, APIConnectionError):
        return "UPSTREAM_UNAVAILABLE"
    if isinstance(root, APITimeoutError):
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
        return "UPSTREAM_ERROR"
    if isinstance(root, AuthenticationError):
        return "AUTH_ERROR"
    if isinstance(root, ValueError):
        return "VALIDATION"
    if isinstance(root, RuntimeError):
        return "RUNTIME"
    return "UNKNOWN"


def format_agent_failure_message(exc: BaseException) -> str:
    """将异常转为用户可读的错误文案。"""
    code = classify_agent_failure(exc)
    root = _unwrap_cause(exc)
    detail = str(root).strip()
    messages = {
        "TIMEOUT": "执行超时，请稍后重试",
        "UPSTREAM_UNAVAILABLE": "模型或向量服务连接失败，请检查网络与 API 配置",
        "RATE_LIMIT": "请求过于频繁，请稍后重试",
        "UPSTREAM_5XX": "上游服务异常，请稍后重试",
        "UPSTREAM_ERROR": "上游模型服务返回异常，请稍后重试",
        "CLIENT_4XX": "请求参数被拒绝，请调整输入后重试",
        "AUTH_ERROR": "API 鉴权失败，请检查 SiliconFlow 等密钥配置",
        "VALIDATION": detail or "请求参数无效",
        "RUNTIME": detail or "服务内部错误",
    }
    base = messages.get(code, detail or "未知错误")
    return f"生成失败: {base}"


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
