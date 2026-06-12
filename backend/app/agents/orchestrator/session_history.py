"""会话历史（内存）。"""
import time
from collections import deque
from typing import Any, Dict, List, Optional

from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import BaseMessage


class WritingSessionHistory(BaseChatMessageHistory):
    """内存存储（Working Memory 上半部）。"""

    def __init__(self, session_id: str, max_messages: int = 20):
        self.session_id = session_id
        self._last_active_at = time.monotonic()
        self.messages: deque = deque(maxlen=max_messages)
        self._last_result: Optional[Dict[str, Any]] = None
        self._last_plan: Optional[Dict[str, Any]] = None
        self.project_id: Optional[str] = None
        self.current_version_id: Optional[str] = None
        self.current_version_label: Optional[str] = None
        self.last_intent: Optional[str] = None

    def touch(self) -> None:
        self._last_active_at = time.monotonic()

    def idle_seconds(self, now: float | None = None) -> float:
        current = now if now is not None else time.monotonic()
        return current - self._last_active_at

    def add_message(self, message: BaseMessage) -> None:
        self.touch()
        self.messages.append(message)

    def get_messages(self) -> List[BaseMessage]:
        return list(self.messages)

    def clear(self) -> None:
        self.messages.clear()
        self._last_result = None
        self._last_plan = None

    def get_last_result(self) -> Optional[Dict[str, Any]]:
        return self._last_result

    def get_last_plan(self) -> Optional[Dict[str, Any]]:
        return self._last_plan

    def update_result(self, result: Dict[str, Any]) -> None:
        if result:
            self._last_result = result

    def update_plan(self, plan: Dict[str, Any]) -> None:
        if plan:
            self._last_plan = plan

    def bind_project(self, project_id: str) -> None:
        self.project_id = project_id

    def bind_version(self, version_id: str, version_label: str) -> None:
        self.current_version_id = version_id
        self.current_version_label = version_label
