"""进程内 session_histories 空闲驱逐。"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .session_history import WritingSessionHistory


def evict_idle_sessions(
    session_histories: dict[str, WritingSessionHistory],
    *,
    ttl_seconds: float,
    protected_session_ids: set[str] | frozenset[str] | None = None,
    now: float | None = None,
) -> list[str]:
    """驱逐超过 TTL 且不在保护集合中的会话，返回被驱逐的 session_id 列表。"""
    if ttl_seconds <= 0:
        return []

    protected = protected_session_ids or set()
    current = now if now is not None else time.monotonic()
    evicted: list[str] = []

    for session_id, history in list(session_histories.items()):
        if session_id in protected:
            continue
        if history.idle_seconds(current) < ttl_seconds:
            continue
        session_histories.pop(session_id, None)
        evicted.append(session_id)

    return evicted
