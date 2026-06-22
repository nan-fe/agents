"""SSE 日志回调辅助。"""

from typing import Awaitable, Callable

LogCallback = Callable[..., Awaitable[None] | None]


async def emit_log(
    log_callback: LogCallback | None,
    agent_key: str,
    message: str,
    *,
    intent: str | None = None,
) -> None:
    """向 log_callback 发送一条日志；agent_key 为内部标识，展示名由 main 层解析。"""
    if not log_callback:
        return

    kwargs = {}
    if intent is not None:
        kwargs["intent"] = intent

    import inspect

    if inspect.iscoroutinefunction(log_callback):
        await log_callback(agent_key, message, **kwargs)
    else:
        log_callback(agent_key, message, **kwargs)
