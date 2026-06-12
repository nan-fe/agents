import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.orchestrator.agent import DialogOrchestratorAgent
from app.config import settings
from app.memory import project_memory
from app.memory.db import close_db, init_db


@pytest.fixture(autouse=True)
def memory_db(monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_URL", "sqlite+aiosqlite:///:memory:")


async def _test_orchestrator_skips_project_stub_without_metadata() -> None:
    await close_db()
    await init_db()

    orchestrator = DialogOrchestratorAgent()
    mock_plan = MagicMock()
    mock_plan.early_exit = {"message": "stub test"}
    mock_plan.intent = "ask_question"

    allowed = MagicMock(allowed=True)
    with (
        patch(
            "app.agents.orchestrator.agent.check_input_security",
            AsyncMock(return_value=allowed),
        ),
        patch.object(
            orchestrator.plan_phase,
            "run",
            AsyncMock(return_value=mock_plan),
        ),
    ):
        result = await orchestrator.run("你好", "session_orchestrator_stub")

    project_id = result["project_id"]
    assert await project_memory.get_project(project_id) is None

    await close_db()


def test_orchestrator_skips_project_stub_without_metadata() -> None:
    asyncio.run(_test_orchestrator_skips_project_stub_without_metadata())
