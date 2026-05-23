import asyncio
import tempfile
from pathlib import Path

from app.services.dialog_stream_store import DialogStream, dialog_stream_store


async def _test_append_event_assigns_incremental_ids() -> None:
    stream = DialogStream(session_id="session_1", prompt="hello")

    first = await stream.append_event({"event": "message", "data": "first"})
    second = await stream.append_event({"event": "message", "data": "second"})

    assert first.event_id == "1"
    assert second.event_id == "2"
    assert first.sse_payload["id"] == "1"
    assert second.sse_payload["id"] == "2"


async def _test_get_events_after_last_event_id() -> None:
    stream = DialogStream(session_id="session_1", prompt="hello")

    await stream.append_event({"event": "message", "data": "first"})
    await stream.append_event({"event": "message", "data": "second"})
    await stream.append_event({"event": "message", "data": "third"})

    replay = stream.get_events_after("1")

    assert [event.event_id for event in replay] == ["2", "3"]


async def _test_snapshot_events_after_replays_and_subscribes() -> None:
    stream = DialogStream(session_id="session_1", prompt="hello")

    await stream.append_event({"event": "message", "data": "first"})
    await stream.append_event({"event": "message", "data": "second"})

    replay, queue = await stream.snapshot_events_after("1")

    assert [event.event_id for event in replay] == ["2"]
    await stream.append_event({"event": "message", "data": "third"})
    queued = await asyncio.wait_for(queue.get(), timeout=1)

    assert queued.event_id == "3"
    await stream.unsubscribe(queue)


async def _test_create_stream_replaces_existing_session() -> None:
    first = await dialog_stream_store.create_stream("session_1", "prompt-a")
    first.task = asyncio.create_task(asyncio.sleep(60))

    second = await dialog_stream_store.create_stream("session_1", "prompt-b")

    assert second.prompt == "prompt-b"
    try:
        await first.task
    except asyncio.CancelledError:
        pass
    assert first.task.cancelled()

    await dialog_stream_store.remove_stream("session_1")


async def _test_persist_and_restore_stream() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        from app.services import dialog_stream_store as store_module

        store = store_module.DialogStreamStore(persist_dir=Path(tmpdir))
        stream = await store.create_stream("session_persist", "prompt-x")
        await stream.append_event({"event": "message", "data": '{"type":"log"}'})

        restored = await store.get_stream("session_persist")
        assert restored is not None
        assert restored.prompt == "prompt-x"
        assert len(restored.events) == 1
        assert restored.events[0].event_id == "1"

        await store.remove_stream("session_persist")
        assert await store.get_stream("session_persist") is None


async def _test_hydrate_marks_complete_when_result_present() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        from app.services import dialog_stream_store as store_module

        store = store_module.DialogStreamStore(persist_dir=Path(tmpdir))
        stream = await store.create_stream("session_done", "prompt-y")
        await stream.append_event(
            {
                "event": "message",
                "data": '{"type":"result","data":{"title":"t","content":"c"}}',
            }
        )
        await store.mark_complete(stream)

        store._streams.pop("session_done", None)
        restored = await store.get_stream("session_done")
        assert restored is not None
        assert restored.is_complete is True
        assert restored.has_result_event() is True

        await store.remove_stream("session_done")


def test_dialog_stream_store() -> None:
    asyncio.run(_test_append_event_assigns_incremental_ids())
    asyncio.run(_test_get_events_after_last_event_id())
    asyncio.run(_test_snapshot_events_after_replays_and_subscribes())
    asyncio.run(_test_create_stream_replaces_existing_session())
    asyncio.run(_test_persist_and_restore_stream())
    asyncio.run(_test_hydrate_marks_complete_when_result_present())
