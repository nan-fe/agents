"""Pipeline 解析：refine 走规则表，fresh task 走 LLM 路由。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.services.orchestrator_llm_service import (
    OrchestratorLLMService,
    RoutingDecision,
)

from .intents import FRESH_TASK_INTENTS, FULL_PIPELINE, PIPELINE_BY_INTENT


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
        return PipelineResolution(
            priority_order=list(routing.priority_order),
            source=source,
            routing=routing,
        )

    routing = fallback_route(intent, f"未知意图 {intent!r}，使用默认创作流程")
    return PipelineResolution(
        priority_order=list(routing.priority_order),
        source="fallback",
        routing=routing,
    )
