import asyncio
from unittest.mock import AsyncMock

import pytest

from app.config import settings
from app.main import _SSE_HEARTBEAT_PAYLOAD, _stream_subscribed_events
from app.services.dialog_stream_store import DialogStream


async def _test_stream_subscribed_events_emits_heartbeat_when_idle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "SSE_HEARTBEAT_INTERVAL_SECONDS", 0.05)
    stream = DialogStream(session_id="session_hb", prompt="hello")
    subscriber = await stream.subscribe()
    request = AsyncMock()
    request.is_disconnected = AsyncMock(return_value=False)

    async def _collect():
        payloads = []
        async for payload in _stream_subscribed_events(request, stream, subscriber):
            payloads.append(payload)
            if len(payloads) >= 2:
                break
        return payloads

    task = asyncio.create_task(_collect())
    await asyncio.sleep(0.02)
    await stream.append_event({"event": "message", "data": "first"})
    payloads = await asyncio.wait_for(task, timeout=2)

    assert payloads[0]["data"] == "first"
    assert payloads[1] == _SSE_HEARTBEAT_PAYLOAD


def test_stream_subscribed_events_emits_heartbeat_when_idle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asyncio.run(_test_stream_subscribed_events_emits_heartbeat_when_idle(monkeypatch))
