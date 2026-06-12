import time

import pytest

from app.agents.orchestrator.agent import DialogOrchestratorAgent
from app.agents.orchestrator.session_eviction import evict_idle_sessions
from app.agents.orchestrator.session_history import WritingSessionHistory
from app.services.dialog_stream_store import dialog_stream_store


def test_evict_idle_sessions_removes_only_expired() -> None:
    histories = {
        "fresh": WritingSessionHistory("fresh"),
        "stale": WritingSessionHistory("stale"),
    }
    now = time.monotonic()
    histories["stale"]._last_active_at = now - 100.0

    evicted = evict_idle_sessions(
        histories,
        ttl_seconds=60.0,
        protected_session_ids={"other"},
        now=now,
    )

    assert evicted == ["stale"]
    assert "fresh" in histories
    assert "stale" not in histories


def test_evict_idle_sessions_respects_protected_ids() -> None:
    histories = {"busy": WritingSessionHistory("busy")}
    now = time.monotonic()
    histories["busy"]._last_active_at = now - 120.0

    evicted = evict_idle_sessions(
        histories,
        ttl_seconds=60.0,
        protected_session_ids={"busy"},
        now=now,
    )

    assert evicted == []
    assert "busy" in histories


def test_evict_idle_sessions_disabled_when_ttl_zero() -> None:
    histories = {"old": WritingSessionHistory("old")}
    histories["old"]._last_active_at = time.monotonic() - 999.0

    evicted = evict_idle_sessions(histories, ttl_seconds=0.0)

    assert evicted == []
    assert "old" in histories


def test_orchestrator_evicts_idle_session_on_next_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.agents.orchestrator.agent.settings.SESSION_IDLE_TTL_SECONDS",
        60.0,
    )
    orchestrator = DialogOrchestratorAgent()
    stale = WritingSessionHistory("session_stale")
    stale._last_active_at = time.monotonic() - 120.0
    orchestrator.session_histories["session_stale"] = stale

    active = orchestrator.get_session_history("session_active")

    assert "session_stale" not in orchestrator.session_histories
    assert active.session_id == "session_active"


def test_orchestrator_keeps_active_generation_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.agents.orchestrator.agent.settings.SESSION_IDLE_TTL_SECONDS",
        60.0,
    )
    orchestrator = DialogOrchestratorAgent()
    stale = WritingSessionHistory("session_generating")
    stale._last_active_at = time.monotonic() - 120.0
    orchestrator.session_histories["session_generating"] = stale

    dialog_stream_store.mark_generation_started("session_generating")
    try:
        orchestrator._evict_idle_sessions()
        assert "session_generating" in orchestrator.session_histories
    finally:
        dialog_stream_store.mark_generation_finished("session_generating")
