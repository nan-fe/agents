import asyncio
import json
import tempfile
from pathlib import Path

from app.services.dialog_stream_store import (
    DialogStream,
    DialogStreamStore,
    stream_matches_request,
)


async def _test_stream_matches_request() -> None:
    stream = DialogStream(
        session_id="session_1",
        prompt="hello",
        user_id="user_a",
        project_id="proj_1",
    )

    assert stream_matches_request(
        stream,
        user_input="hello",
        user_id="user_a",
        project_id="proj_1",
    )
    assert not stream_matches_request(
        stream,
        user_input="hello",
        user_id="user_b",
        project_id="proj_1",
    )
    assert not stream_matches_request(
        stream,
        user_input="hello",
        user_id="user_a",
        project_id="proj_2",
    )
    assert not stream_matches_request(
        stream,
        user_input="other",
        user_id="user_a",
        project_id="proj_1",
    )


async def _test_completed_stream_not_reused_for_different_user() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        store = DialogStreamStore(persist_dir=Path(tmpdir))
        session_id = "session_shared"

        stream = await store.create_stream(
            session_id,
            "same prompt",
            user_id="user_a",
            project_id="proj_1",
        )
        await stream.append_event(
            {
                "event": "message",
                "data": json.dumps({"type": "result", "data": {"title": "A"}}),
            }
        )
        await store.mark_complete(stream)

        restored = await store.get_stream(session_id)
        assert restored is not None
        assert stream_matches_request(
            restored,
            user_input="same prompt",
            user_id="user_a",
            project_id="proj_1",
        )
        assert not stream_matches_request(
            restored,
            user_input="same prompt",
            user_id="user_b",
            project_id="proj_1",
        )

        await store.remove_stream(session_id)


def test_dialog_stream_reuse_identity() -> None:
    asyncio.run(_test_stream_matches_request())
    asyncio.run(_test_completed_stream_not_reused_for_different_user())
