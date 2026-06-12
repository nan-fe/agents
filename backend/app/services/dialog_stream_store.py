import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

DEFAULT_STREAM_DIR = Path(__file__).resolve().parents[1] / "data" / "dialog_streams"


def _safe_session_filename(session_id: str) -> str:
    return re.sub(r"[^\w\-.]", "_", session_id)


@dataclass
class StreamEvent:
    event_id: str
    sse_payload: dict[str, Any]


@dataclass
class DialogStream:
    session_id: str
    prompt: str
    events: list[StreamEvent] = field(default_factory=list)
    next_event_id: int = 1
    task: Optional[asyncio.Task] = None
    is_complete: bool = False
    _subscriber_queues: list[asyncio.Queue] = field(default_factory=list)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _store: Optional["DialogStreamStore"] = field(default=None, repr=False)

    def has_event(self, event_id: str) -> bool:
        return any(event.event_id == event_id for event in self.events)

    def get_events_after(self, last_event_id: str) -> list[StreamEvent]:
        found = False
        result: list[StreamEvent] = []
        for event in self.events:
            if found:
                result.append(event)
            elif event.event_id == last_event_id:
                found = True
        return result

    def has_result_event(self) -> bool:
        for event in self.events:
            raw_data = event.sse_payload.get("data")
            if not isinstance(raw_data, str):
                continue
            try:
                message = json.loads(raw_data)
            except json.JSONDecodeError:
                continue
            if message.get("type") == "result":
                return True
        return False

    async def append_event(self, payload: dict[str, Any]) -> StreamEvent:
        async with self._lock:
            event_id = str(self.next_event_id)
            self.next_event_id += 1
            sse_payload = {**payload, "id": event_id}
            sse_payload.pop("sep", None)
            stream_event = StreamEvent(event_id=event_id, sse_payload=sse_payload)
            self.events.append(stream_event)
            for queue in self._subscriber_queues:
                await queue.put(stream_event)
        if self._store is not None:
            # 落盘不阻塞 SSE 推送（同步 write_text 会卡住 event loop）
            asyncio.create_task(self._store._persist_stream(self))
        return stream_event
        

    async def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        async with self._lock:
            self._subscriber_queues.append(queue)
        return queue

    async def unsubscribe(self, queue: asyncio.Queue) -> None:
        async with self._lock:
            if queue in self._subscriber_queues:
                self._subscriber_queues.remove(queue)

    async def snapshot_events_after(self, last_event_id: str) -> tuple[list[StreamEvent], asyncio.Queue]:
        async with self._lock:
            events = self.get_events_after(last_event_id)
            queue: asyncio.Queue = asyncio.Queue()
            self._subscriber_queues.append(queue)
            return events, queue


class DialogStreamStore:
    def __init__(self, persist_dir: Optional[Path] = None) -> None:
        self._streams: dict[str, DialogStream] = {}
        self._active_generations: set[str] = set()
        self._lock = asyncio.Lock()
        self._io_lock = asyncio.Lock()
        self._persist_dir = persist_dir or DEFAULT_STREAM_DIR
        self._persist_dir.mkdir(parents=True, exist_ok=True)

    def mark_generation_started(self, session_id: str) -> None:
        self._active_generations.add(session_id)

    def mark_generation_finished(self, session_id: str) -> None:
        self._active_generations.discard(session_id)

    def active_generation_session_ids(self) -> frozenset[str]:
        return frozenset(self._active_generations)

    def _persist_path(self, session_id: str) -> Path:
        return self._persist_dir / f"{_safe_session_filename(session_id)}.json"

    async def _persist_stream(self, stream: DialogStream) -> None:
        payload = {
            "session_id": stream.session_id,
            "prompt": stream.prompt,
            "next_event_id": stream.next_event_id,
            "is_complete": stream.is_complete,
            "events": [
                {"event_id": event.event_id, "sse_payload": event.sse_payload}
                for event in stream.events
            ],
        }
        path = self._persist_path(stream.session_id)
        async with self._io_lock:
            path.write_text(
                json.dumps(payload, ensure_ascii=False),
                encoding="utf-8",
            )

    def _hydrate_stream(self, data: dict[str, Any]) -> DialogStream:
        stream = DialogStream(
            session_id=data["session_id"],
            prompt=data["prompt"],
            next_event_id=int(data.get("next_event_id", 1)),
            is_complete=bool(data.get("is_complete", False)),
            _store=self,
        )
        for item in data.get("events", []):
            stream.events.append(
                StreamEvent(
                    event_id=str(item["event_id"]),
                    sse_payload=item["sse_payload"],
                )
            )
        if stream.has_result_event():
            stream.is_complete = True
        return stream

    async def _load_persisted_stream(self, session_id: str) -> Optional[DialogStream]:
        path = self._persist_path(session_id)
        if not path.exists():
            return None
        async with self._io_lock:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                logger.exception("加载 SSE 缓冲失败 session_id=%s", session_id)
                return None
        if data.get("session_id") != session_id:
            return None
        return self._hydrate_stream(data)

    async def get_stream(self, session_id: str) -> Optional[DialogStream]:
        async with self._lock:
            stream = self._streams.get(session_id)
            if stream is not None:
                return stream

        persisted = await self._load_persisted_stream(session_id)
        if persisted is None:
            return None

        async with self._lock:
            existing = self._streams.get(session_id)
            if existing is not None:
                return existing
            self._streams[session_id] = persisted
            logger.info(
                "从磁盘恢复 SSE 缓冲 session_id=%s events=%d",
                session_id,
                len(persisted.events),
            )
            return persisted

    async def create_stream(self, session_id: str, prompt: str) -> DialogStream:
        async with self._lock:
            existing = self._streams.get(session_id)
            if existing and existing.task and not existing.task.done():
                existing.task.cancel()

            stream = DialogStream(session_id=session_id, prompt=prompt, _store=self)
            self._streams[session_id] = stream
        await self._persist_stream(stream)
        return stream

    async def remove_stream(self, session_id: str) -> None:
        async with self._lock:
            self._streams.pop(session_id, None)
        path = self._persist_path(session_id)
        async with self._io_lock:
            if path.exists():
                path.unlink()

    async def mark_complete(self, stream: DialogStream) -> None:
        stream.is_complete = True
        await self._persist_stream(stream)


dialog_stream_store = DialogStreamStore()
