"""统一规划阶段：意图识别 + 内容策划 + pipeline 解析。"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from app.config import settings
from app.services.orchestrator_llm_service import (
    IntentAnalysisTimeoutError,
    OrchestratorLLMService,
    RoutingDecision,
)
from app.utils.display_labels import format_agent_pipeline, intent_display_label
from app.utils.log_callback import emit_log

from ..execution_context import ExecutionContext
from ..session_history import WritingSessionHistory
from .content_strategist_agent import ContentStrategistAgent
from .intents import (
    is_fresh_task_intent,
    should_run_content_strategist,
)
from .pipeline_resolver import resolve_pipeline

ASK_QUESTION_RESPONSE: Dict[str, Any] = {
    "title": "",
    "content": "",
    "hashtags": [],
    "image_url": "",
    "message": (
        "抱歉，我无法回答问题。这是一个小红书文案生成平台，"
        "请输入您想要生成的文案要求，例如：帮我写一篇关于防晒霜的推荐文案"
    ),
}


@dataclass
class PlanPhaseResult:
    """规划阶段输出。"""

    intent: str
    pipeline_order: List[str]
    routing: RoutingDecision
    replanned: bool
    early_exit: Optional[Dict[str, Any]] = None


class PlanPhaseRunner:
    """intent → 内容策划（按需）→ resolve_pipeline（refine 规则 / fresh LLM）。"""

    def __init__(
        self,
        content_strategist_agent: ContentStrategistAgent,
        llm_service: OrchestratorLLMService,
    ):
        self.content_strategist_agent = content_strategist_agent
        self.llm_service = llm_service

    async def run(
        self,
        user_input: str,
        session_history: WritingSessionHistory,
        context: ExecutionContext,
        log_callback: Optional[Callable] = None,
    ) -> PlanPhaseResult:
        await emit_log(log_callback, "Orchestrator", "规划阶段：识别意图…")

        try:
            intent = await self.llm_service.analyze_intent(
                user_input, session_history.messages
            )
        except IntentAnalysisTimeoutError as e:
            await emit_log(log_callback, "Orchestrator", str(e))
            return PlanPhaseResult(
                intent="",
                pipeline_order=[],
                routing=RoutingDecision(
                    task_type="error",
                    agents_to_call=[],
                    reasoning=str(e),
                    priority_order=[],
                ),
                replanned=False,
                early_exit=e.to_early_exit(),
            )

        await emit_log(
            log_callback,
            "Orchestrator",
            f"规划阶段：意图「{intent_display_label(intent)}」",
            intent=intent,
        )

        if intent == "ask_question":
            await emit_log(
                log_callback,
                "Orchestrator",
                "很抱歉，我无法回答您的问题，你可以换个问题，比如让我写商品的宣传文案",
                intent=intent,
            )
            return PlanPhaseResult(
                intent=intent,
                pipeline_order=[],
                routing=RoutingDecision(
                    task_type="ask_question",
                    agents_to_call=[],
                    reasoning="问答意图，不执行创作流水线",
                    priority_order=[],
                ),
                replanned=False,
                early_exit=dict(ASK_QUESTION_RESPONSE),
            )

        replanned = await self._resolve_planning(
            context, session_history, intent, user_input, log_callback
        )
        await self._load_session_artifacts(
            context, session_history, intent, log_callback
        )

        await emit_log(log_callback, "Orchestrator", "规划阶段：解析 pipeline…")
        resolution = await resolve_pipeline(
            intent, user_input, context.get_planning(), self.llm_service
        )
        routing = resolution.routing
        pipeline_order = list(resolution.priority_order)

        pipeline_labels = format_agent_pipeline(pipeline_order)
        await emit_log(
            log_callback,
            "Orchestrator",
            f"规划阶段完成（{resolution.source}），执行：{' → '.join(pipeline_labels)}",
            intent=intent,
        )

        return PlanPhaseResult(
            intent=intent,
            pipeline_order=pipeline_order,
            routing=routing,
            replanned=replanned,
        )

    async def _resolve_planning(
        self,
        context: ExecutionContext,
        session_history: WritingSessionHistory,
        intent: str,
        user_input: str,
        log_callback: Optional[Callable],
    ) -> bool:
        last_plan = session_history.get_last_plan()
        if should_run_content_strategist(intent, last_plan is not None):
            planning_result = await asyncio.wait_for(
                self.content_strategist_agent.run(
                    user_input, log_callback, history=""
                ),
                timeout=settings.AGENT_TIMEOUT_PLANNER_AGENT_SECONDS,
            )
            context.set_planning(planning_result)
            if is_fresh_task_intent(intent):
                await emit_log(
                    log_callback,
                    "Orchestrator",
                    "新任务/换题：已重新策划",
                )
            else:
                await emit_log(
                    log_callback,
                    "Orchestrator",
                    "未找到历史策划，已自动重建",
                )
            return True

        context.load_from_dict({"planning": last_plan})
        await emit_log(log_callback, "Orchestrator", "复用历史策划")
        return False

    async def _load_session_artifacts(
        self,
        context: ExecutionContext,
        session_history: WritingSessionHistory,
        intent: str,
        log_callback: Optional[Callable],
    ) -> None:
        if is_fresh_task_intent(intent):
            return

        last_result = session_history.get_last_result()
        if not last_result:
            return

        context.load_from_dict({
            "copywriting": {
                "title": last_result.get("title", ""),
                "content": last_result.get("content", ""),
                "hashtags": last_result.get("hashtags", []),
            },
            "image": {
                "image_url": last_result.get("image_url", ""),
                "prompt": last_result.get(
                    "prompt", last_result.get("image_prompt", "")
                ),
            },
        })
        context.set_last_result(last_result)
        await emit_log(log_callback, "Orchestrator", "已加载上轮文案与配图")
