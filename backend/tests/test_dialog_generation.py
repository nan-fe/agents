import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from app.main import _run_dialog_generation
from app.services.dialog_stream_store import dialog_stream_store


def _parse_result_event(stream) -> dict:
    result_events = [
        event
        for event in stream.events
        if json.loads(event.sse_payload["data"]).get("type") == "result"
    ]
    assert len(result_events) == 1
    return json.loads(result_events[0].sse_payload["data"])["data"]


async def _test_run_dialog_generation_emits_result_on_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_id = "session_success"
    prompt = "写一篇小红书"
    stream = await dialog_stream_store.create_stream(session_id, prompt)

    success_result = {
        "title": "标题",
        "content": "正文",
        "hashtags": ["#测试"],
        "image_url": "",
        "project_id": "proj-1",
    }
    monkeypatch.setattr(
        "app.main.orchestrator.run",
        AsyncMock(return_value=success_result),
    )

    await _run_dialog_generation(stream, prompt, session_id, project_id="proj-1")

    assert stream.is_complete
    assert _parse_result_event(stream) == success_result
    await dialog_stream_store.remove_stream(session_id)


async def _test_run_dialog_generation_timeout_emits_error_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_id = "session_timeout"
    prompt = "写一篇小红书"
    stream = await dialog_stream_store.create_stream(session_id, prompt)

    monkeypatch.setattr(
        "app.main.orchestrator.run",
        AsyncMock(side_effect=TimeoutError()),
    )

    await _run_dialog_generation(stream, prompt, session_id)

    result = _parse_result_event(stream)
    assert result["error_code"] == "TIMEOUT"
    assert "超时" in result["message"]
    await dialog_stream_store.remove_stream(session_id)


async def _test_run_dialog_generation_holds_semaphore_until_complete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app import main as main_module

    session_id = "session_sem"
    prompt = "prompt"
    stream = await dialog_stream_store.create_stream(session_id, prompt)
    entered = asyncio.Event()
    release = asyncio.Event()

    async def _slow_run(*_args, **_kwargs):
        entered.set()
        await release.wait()
        return {
            "title": "",
            "content": "ok",
            "hashtags": [],
            "image_url": "",
        }

    monkeypatch.setattr("app.main.orchestrator.run", _slow_run)
    monkeypatch.setattr(
        main_module,
        "_dialog_generation_sem",
        asyncio.Semaphore(1),
    )

    task = asyncio.create_task(_run_dialog_generation(stream, prompt, session_id))

    await asyncio.wait_for(entered.wait(), timeout=1)
    assert main_module._dialog_generation_sem.locked()

    release.set()
    await asyncio.wait_for(task, timeout=1)
    assert not main_module._dialog_generation_sem.locked()
    await dialog_stream_store.remove_stream(session_id)


def test_run_dialog_generation_emits_result_on_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asyncio.run(_test_run_dialog_generation_emits_result_on_success(monkeypatch))


def test_run_dialog_generation_timeout_emits_error_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asyncio.run(_test_run_dialog_generation_timeout_emits_error_result(monkeypatch))


def test_run_dialog_generation_holds_semaphore_until_complete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asyncio.run(_test_run_dialog_generation_holds_semaphore_until_complete(monkeypatch))
