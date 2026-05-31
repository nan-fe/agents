from unittest.mock import AsyncMock, MagicMock, patch
import asyncio

import pytest

from app.agents.orchestrator.agent import DialogOrchestratorAgent
from app.agents.orchestrator.agent_input_builder import AgentInputBuilder
from app.agents.orchestrator.execution_context import ExecutionContext
from app.models.schemas import ReviewResult


@pytest.fixture
def orchestrator() -> DialogOrchestratorAgent:
    with patch.object(DialogOrchestratorAgent, "__init__", lambda self, *a, **k: None):
        agent = DialogOrchestratorAgent.__new__(DialogOrchestratorAgent)
        agent.agent_map = {
            "CopywriterAgent": MagicMock(),
            "ImageAgent": MagicMock(),
            "ReviewerAgent": MagicMock(),
        }
        agent.agent_executor = MagicMock()
        return agent


def test_agent_input_builder_repair_injects_feedback() -> None:
    context = ExecutionContext()
    context.review.feedback = "标题夸大宣传"
    context.review.corrections = {"copywriting": {"title": "改标题"}}
    builder = AgentInputBuilder(context, "写一篇防晒文案", repair_mode=True)
    payload = builder.build_copywriter_input()
    assert "审核修复要求" in payload["user_input"]
    assert "标题夸大宣传" in payload["user_input"]


def test_agent_input_builder_repair_image_history() -> None:
    context = ExecutionContext()
    context.review.feedback = "配图不当"
    context.review.corrections = {"image": {"prompt": "自然光产品图"}}
    builder = AgentInputBuilder(context, "换图", repair_mode=True)
    payload = builder.build_image_input()
    assert "配图不当" in payload["history"]
    assert "自然光产品图" in payload["history"]


def test_build_final_result_policy_block_clears_content() -> None:
    context = ExecutionContext()
    context.copywriting.title = "违规标题"
    context.copywriting.content = "违规内容"
    context.review.review_executed = True
    context.review.approved = False
    context.review.failure_category = "policy_block"
    context.review.feedback = "违反平台规则"
    context.review.review_status = "policy_block"

    final = context.build_final_result()
    assert final["title"] == ""
    assert final["content"] == ""
    assert final["error_code"] == "POLICY_BLOCK"


def test_run_review_repair_loop_skipped_when_review_not_failed(
    orchestrator: DialogOrchestratorAgent,
) -> None:
    context = ExecutionContext()
    context.mark_review_skipped()
    orchestrator._execute_agent_pipeline = AsyncMock()

    asyncio.run(orchestrator._run_review_repair_loop(context, "input", None))

    orchestrator._execute_agent_pipeline.assert_not_called()


def test_run_review_repair_loop_runs_copywriter_on_failed_review(
    orchestrator: DialogOrchestratorAgent,
) -> None:
    context = ExecutionContext()
    context.review.review_executed = True
    context.review.approved = False
    context.review.review_status = "failed"
    context.review.failure_category = "copywriting"
    context.review.feedback = "标题需修改"

    async def fake_pipeline(agent_names, ctx, user_input, log_callback, builder=None):
        if "ReviewerAgent" in agent_names:
            ctx.set_review_from_result(
                ReviewResult(approved=True, feedback="已通过")
            )

    orchestrator._execute_agent_pipeline = AsyncMock(side_effect=fake_pipeline)

    asyncio.run(orchestrator._run_review_repair_loop(context, "写一篇文案", None))

    orchestrator._execute_agent_pipeline.assert_called_once()
    call_args = orchestrator._execute_agent_pipeline.call_args
    assert call_args[0][0] == ["CopywriterAgent", "ReviewerAgent"]
    assert call_args[1]["builder"].repair_mode is True
    assert context.review.approved is True


def test_run_review_repair_loop_skips_on_review_error(
    orchestrator: DialogOrchestratorAgent,
) -> None:
    context = ExecutionContext()
    context.review.review_executed = True
    context.review.approved = False
    context.review.review_status = "error"
    context.review.failure_category = "review_error"

    orchestrator._execute_agent_pipeline = AsyncMock()

    asyncio.run(orchestrator._run_review_repair_loop(context, "input", None))

    orchestrator._execute_agent_pipeline.assert_not_called()
