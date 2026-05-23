"""SSE 断点续传状态机。

约定：
- REPLAY_DONE         : 已有 result → 只回放
- SUBSCRIBE_RUNNING   : 后台 task 仍在 → 回放 + 订阅
- ORPHAN_RESTART_FULL : task 已丢（如 --reload）→ 重建 stream，全流程从 event_id=1 开始，
                        前端按 event_id 去重
"""

from enum import Enum

from app.services.dialog_stream_store import DialogStream


class ResumePhase(str, Enum):
    REPLAY_DONE = "replay_done"
    SUBSCRIBE_RUNNING = "subscribe_running"
    ORPHAN_RESTART_FULL = "orphan_restart_full"


def is_orphaned_stream(stream: DialogStream) -> bool:
    """未完成、无存活 task、且无 result 的 stream。"""
    if stream.is_complete:
        return False
    if stream.task is not None and not stream.task.done():
        return False
    return not stream.has_result_event()

def resolve_resume_phase(stream: DialogStream) -> ResumePhase:
    """回放 last_event_id 之后，决定后续动作。"""
    if stream.is_complete or stream.has_result_event():
        return ResumePhase.REPLAY_DONE
    if is_orphaned_stream(stream):
        return ResumePhase.ORPHAN_RESTART_FULL
    return ResumePhase.SUBSCRIBE_RUNNING
