import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import _run_dialog_generation, app
from app.models.schemas import SSEMessage
from app.services.dialog_stream_store import dialog_stream_store


def _log_payload(text: str) -> str:
    message = SSEMessage(
        type="log",
        data={"from": "Orchestrator", "message": text, "timestamp": 1},
    )
    return message.model_dump_json()


def _result_payload() -> str:
    message = SSEMessage(
        type="result",
        data={
            "title": "t",
            "content": "c",
            "hashtags": [],
            "image_url": "",
        },
    )
    return message.model_dump_json()


async def _collect_sse_events(response) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    current_id: str | None = None
    current_data: str | None = None

    async for line in response.aiter_lines():
        if line.startswith("id:"):
            current_id = line.split(":", 1)[1].strip()
            continue
        if line.startswith("data:"):
            current_data = line.split(":", 1)[1].strip()
            continue
        if not line.strip() and current_data is not None:
            events.append({"id": current_id, "data": json.loads(current_data)})
            current_id = None
            current_data = None

    if current_data is not None:
        events.append({"id": current_id, "data": json.loads(current_data)})

    return events


async def _seed_stream(session_id: str, prompt: str, count: int) -> None:
    stream = await dialog_stream_store.create_stream(session_id, prompt)
    for index in range(1, count + 1):
        await stream.append_event(
            {"event": "message", "data": _log_payload(f"log-{index}")}
        )


async def _test_resume_replays_only_events_after_last_event_id() -> None:
    session_id = "session_resume_replay"
    prompt = "prompt-a"
    await _seed_stream(session_id, prompt, 5)
    stream = await dialog_stream_store.get_stream(session_id)
    assert stream is not None
    await stream.append_event(
        {"event": "message", "data": _result_payload()}
    )
    stream.is_complete = True
    await dialog_stream_store.mark_complete(stream)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/dialog/generate",
            json={
                "prompt": prompt,
                "session_id": session_id,
                "last_event_id": "3",
            },
        )
        events = await _collect_sse_events(response)

    await dialog_stream_store.remove_stream(session_id)

    assert [event["id"] for event in events] == ["4", "5", "6"]
    assert events[-1]["data"]["type"] == "result"


async def _test_resume_orphan_restarts_full_pipeline_from_id_1(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_id = "session_resume_orphan"
    prompt = "prompt-b"
    await _seed_stream(session_id, prompt, 7)
    stream = await dialog_stream_store.get_stream(session_id)
    assert stream is not None
    stream.task = None

    async def _fake_run_generation(
        target_stream, user_input, session_id_arg, **kwargs
    ):
        await target_stream.append_event(
            {"event": "message", "data": _log_payload("restart-1")}
        )
        await target_stream.append_event(
            {"event": "message", "data": _log_payload("restart-2")}
        )
        await target_stream.append_event(
            {"event": "message", "data": _result_payload()}
        )

    monkeypatch.setattr(
        "app.main._run_dialog_generation",
        _fake_run_generation,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/dialog/generate",
            json={
                "prompt": prompt,
                "session_id": session_id,
                "last_event_id": "7",
            },
        )
        events = await _collect_sse_events(response)

    await dialog_stream_store.remove_stream(session_id)

    assert [event["id"] for event in events] == ["1", "2", "3"]
    assert events[0]["data"]["data"]["message"] == "restart-1"
    assert events[-1]["data"]["type"] == "result"


async def _test_resume_subscribes_running_task_without_duplicating_replay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_id = "session_resume_running"
    prompt = "prompt-c"
    await _seed_stream(session_id, prompt, 5)
    stream = await dialog_stream_store.get_stream(session_id)
    assert stream is not None

    gate = asyncio.Event()

    async def _slow_run_generation(
        target_stream, user_input, session_id_arg, **kwargs
    ):
        await gate.wait()
        await target_stream.append_event(
            {"event": "message", "data": _log_payload("live-6")}
        )
        await target_stream.append_event(
            {"event": "message", "data": _result_payload()}
        )

    monkeypatch.setattr(
        "app.main._run_dialog_generation",
        _slow_run_generation,
    )
    monkeypatch.setattr(
        "app.main.check_input_security",
        AsyncMock(return_value=type("R", (), {"allowed": True})()),
    )

    stream.task = asyncio.create_task(_run_dialog_generation(stream, prompt, session_id))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/dialog/generate",
            json={
                "prompt": prompt,
                "session_id": session_id,
                "last_event_id": "5",
            },
        )
        gate.set()
        events = await _collect_sse_events(response)

    if stream.task is not None and not stream.task.done():
        stream.task.cancel()
        try:
            await stream.task
        except asyncio.CancelledError:
            pass

    await dialog_stream_store.remove_stream(session_id)

    assert [event["id"] for event in events] == ["6", "7"]
    assert events[0]["data"]["data"]["message"] == "live-6"


def test_resume_replays_only_events_after_last_event_id() -> None:
    asyncio.run(_test_resume_replays_only_events_after_last_event_id())


def test_resume_orphan_restarts_full_pipeline_from_id_1(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asyncio.run(_test_resume_orphan_restarts_full_pipeline_from_id_1(monkeypatch))


def test_resume_subscribes_running_task_without_duplicating_replay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asyncio.run(
        _test_resume_subscribes_running_task_without_duplicating_replay(monkeypatch)
    )
