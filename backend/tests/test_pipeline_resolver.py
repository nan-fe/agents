import asyncio
from unittest.mock import AsyncMock, MagicMock

from app.agents.orchestrator.planning import PIPELINE_BY_INTENT
from app.agents.orchestrator.planning.pipeline_resolver import (
    fallback_route,
    resolve_pipeline,
)
from app.services.orchestrator_llm_service import RoutingDecision


def test_fallback_route_refine_content_short_chain() -> None:
    routing = fallback_route("refine_content", "timeout")
    assert routing.priority_order == ["CopywriterAgent", "ReviewerAgent"]
    assert "ImageAgent" not in routing.priority_order
    assert routing.reasoning.startswith("[fallback]")


def test_fallback_route_refine_image_short_chain() -> None:
    routing = fallback_route("refine_image", "error")
    assert routing.priority_order == ["ImageAgent", "ReviewerAgent"]
    assert "CopywriterAgent" not in routing.priority_order


def test_fallback_route_fresh_task_full_pipeline() -> None:
    routing = fallback_route("new_task", "timeout")
    assert routing.priority_order == [
        "CopywriterAgent",
        "ImageAgent",
        "ReviewerAgent",
    ]


def test_resolve_pipeline_refine_content_skips_llm() -> None:
    llm_service = MagicMock()
    llm_service.route_task = AsyncMock()

    result = asyncio.run(
        resolve_pipeline(
            "refine_content",
            "改语气活泼一点",
            {"topic": "防晒霜"},
            llm_service,
        )
    )

    assert result.source == "rule"
    assert result.priority_order == PIPELINE_BY_INTENT["refine_content"]
    llm_service.route_task.assert_not_called()


def test_resolve_pipeline_refine_image_skips_llm() -> None:
    llm_service = MagicMock()
    llm_service.route_task = AsyncMock()

    result = asyncio.run(
        resolve_pipeline(
            "refine_image",
            "换一张海边背景",
            {"topic": "防晒霜"},
            llm_service,
        )
    )

    assert result.source == "rule"
    assert result.priority_order == PIPELINE_BY_INTENT["refine_image"]
    llm_service.route_task.assert_not_called()


def test_resolve_pipeline_fresh_task_uses_llm() -> None:
    llm_service = MagicMock()
    llm_service.route_task = AsyncMock(
        return_value=RoutingDecision(
            task_type="content_creation",
            agents_to_call=[
                "RagAgent",
                "CopywriterAgent",
                "ImageAgent",
                "ReviewerAgent",
            ],
            reasoning="需要商品检索",
            priority_order=[
                "RagAgent",
                "CopywriterAgent",
                "ImageAgent",
                "ReviewerAgent",
            ],
        )
    )

    result = asyncio.run(
        resolve_pipeline(
            "new_task",
            "写一篇防晒霜推荐",
            {"topic": "防晒霜"},
            llm_service,
        )
    )

    assert result.source == "llm"
    assert "RagAgent" in result.priority_order
    llm_service.route_task.assert_awaited_once()


def test_resolve_pipeline_unknown_intent_fallback() -> None:
    llm_service = MagicMock()
    llm_service.route_task = AsyncMock()

    result = asyncio.run(
        resolve_pipeline(
            "weird_intent",
            "随便说点什么",
            {},
            llm_service,
        )
    )

    assert result.source == "fallback"
    assert result.priority_order == [
        "CopywriterAgent",
        "ImageAgent",
        "ReviewerAgent",
    ]
    llm_service.route_task.assert_not_called()
