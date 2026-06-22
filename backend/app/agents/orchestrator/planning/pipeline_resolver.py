"""Pipeline 解析：refine 走规则表，fresh task 走 LLM 路由。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from langsmith import Client, traceable
from langsmith.run_helpers import get_current_run_tree

from app.config import settings
from app.services.orchestrator_llm_service import (
    OrchestratorLLMService,
    RoutingDecision,
)

from .intents import FRESH_TASK_INTENTS, FULL_PIPELINE, PIPELINE_BY_INTENT

_langsmith_client = Client(api_key=settings.LANGCHAIN_API_KEY)


def _report_fallback_route_safe(intent: str, reason: str) -> None:
    """上报 fallback 路由指标；失败时静默，不影响主流程。"""
    try:
        run_tree = get_current_run_tree()
        if not run_tree:
            return
        _langsmith_client.create_feedback(
            run_id=run_tree.id,
            key="fallback_route",
            score=1,
            comment=f"intent={intent}; reason={reason}",
        )
    except Exception:
        return


def fallback_route(intent: str, reason: str) -> RoutingDecision:
    """LLM 路由失败时的 intent-aware 兜底。"""
    if intent in PIPELINE_BY_INTENT:
        order = list(PIPELINE_BY_INTENT[intent])
    else:
        order = list(FULL_PIPELINE)
    return RoutingDecision(
        task_type=intent or "new_task",
        agents_to_call=order,
        reasoning=f"[fallback] {reason}",
        priority_order=order,
    )


def _rule_routing(intent: str, order: list[str]) -> RoutingDecision:
    return RoutingDecision(
        task_type=intent,
        agents_to_call=list(order),
        reasoning=f"intent={intent} 固定 pipeline",
        priority_order=list(order),
    )


@dataclass
class PipelineResolution:
    priority_order: list[str]
    source: Literal["rule", "llm", "fallback"]
    routing: RoutingDecision


@traceable(name="orchestrator.resolve_pipeline", run_type="chain")
async def resolve_pipeline(
    intent: str,
    user_input: str,
    planning: dict,
    llm_service: OrchestratorLLMService,
) -> PipelineResolution:
    """按意图解析执行 pipeline。"""
    if intent in PIPELINE_BY_INTENT:
        order = PIPELINE_BY_INTENT[intent]
        return PipelineResolution(
            priority_order=list(order),
            source="rule",
            routing=_rule_routing(intent, order),
        )

    if intent in FRESH_TASK_INTENTS:
        routing = await llm_service.route_task(user_input, planning, intent)
        source: Literal["llm", "fallback"] = (
            "fallback" if routing.reasoning.startswith("[fallback]") else "llm"
        )
        if source == "fallback":
            _report_fallback_route_safe(intent, routing.reasoning)
        return PipelineResolution(
            priority_order=list(routing.priority_order),
            source=source,
            routing=routing,
        )

    routing = fallback_route(intent, f"未知意图 {intent!r}，使用默认创作流程")
    _report_fallback_route_safe(intent, routing.reasoning)
    return PipelineResolution(
        priority_order=list(routing.priority_order),
        source="fallback",
        routing=routing,
    )
