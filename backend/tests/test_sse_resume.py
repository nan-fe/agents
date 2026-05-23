import asyncio

from app.services.dialog_stream_store import DialogStream
from app.services.sse_resume import ResumePhase, is_orphaned_stream, resolve_resume_phase


def _stream(**kwargs) -> DialogStream:
    return DialogStream(session_id="s1", prompt="p", **kwargs)


def test_orphaned_when_incomplete_without_task_or_result() -> None:
    stream = _stream(is_complete=False, task=None)
    assert is_orphaned_stream(stream) is True
    assert resolve_resume_phase(stream) is ResumePhase.ORPHAN_RESTART_FULL


async def _test_running_when_task_alive() -> None:
    stream = _stream(is_complete=False)
    stream.task = asyncio.create_task(asyncio.sleep(60))
    try:
        assert is_orphaned_stream(stream) is False
        assert resolve_resume_phase(stream) is ResumePhase.SUBSCRIBE_RUNNING
    finally:
        stream.task.cancel()
        try:
            await stream.task
        except asyncio.CancelledError:
            pass


def test_running_when_task_alive() -> None:
    asyncio.run(_test_running_when_task_alive())


async def _test_complete_stream_replay_done() -> None:
    stream = _stream(is_complete=True, task=None)
    await stream.append_event(
        {
            "event": "message",
            "data": '{"type":"result","data":{"title":"t","content":"c"}}',
        }
    )
    assert resolve_resume_phase(stream) is ResumePhase.REPLAY_DONE


def test_complete_stream_replay_done() -> None:
    asyncio.run(_test_complete_stream_replay_done())


def test_orphan_not_confused_with_complete_without_result() -> None:
    """task 结束但未写 result 时 is_complete 可能为 True，不应判 orphan。"""
    stream = _stream(is_complete=True, task=None)
    assert is_orphaned_stream(stream) is False
    assert resolve_resume_phase(stream) is ResumePhase.REPLAY_DONE
