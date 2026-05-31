from app.agents.planner_agent import PlannerAgent
from app.agents.copywriter_agent import CopywriterAgent
from app.agents.image_agent import ImageAgent
from app.agents.reviewer_agent import ReviewerAgent
from app.agents.product_rag_system.agent import ProductRagAgent
from app.services.orchestrator_llm_service import OrchestratorLLMService
from app.config import settings
from app.security.input_guard import check_input_security, safety_rejection_payload
from app.utils.retry_policy import classify_agent_failure
from app.utils.log_callback import emit_log
from .execution_context import ExecutionContext
from .agent_input_builder import AgentInputBuilder
from .agent_executor import AgentExecutor
from .result_mapper import ResultMapper
from .plan_phase import (
    FRESH_TASK_INTENTS,
    PlanPhaseRunner,
    is_fresh_task_intent,
)
from .review_repair_router import (
    content_agents_ran,
    route_review_failure,
)
from .session_history import WritingSessionHistory
from typing import Optional, Callable, Dict, List
import time
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv

load_dotenv()

# 兼容既有测试与导入
__all__ = [
    "DialogOrchestratorAgent",
    "WritingSessionHistory",
    "FRESH_TASK_INTENTS",
    "is_fresh_task_intent",
]


class DialogOrchestratorAgent:
    """Agent协调器"""

    def __init__(self):
        """初始化协调器"""
        self.planner_agent = PlannerAgent()
        self.copywriter_agent = CopywriterAgent()
        self.image_agent = ImageAgent()
        self.reviewer_agent = ReviewerAgent()
        self.rag_agent = ProductRagAgent()
        self.llm_service = OrchestratorLLMService()
        self.plan_phase = PlanPhaseRunner(self.planner_agent, self.llm_service)

        self.agent_map = {
            "PlannerAgent": self.planner_agent,
            "CopywriterAgent": self.copywriter_agent,
            "ImageAgent": self.image_agent,
            "ReviewerAgent": self.reviewer_agent,
            "RagAgent": self.rag_agent,
        }

        self.agent_executor = AgentExecutor(self.agent_map)
        self.session_histories: Dict[str, WritingSessionHistory] = {}

    def get_session_history(self, session_id: str) -> WritingSessionHistory:
        if session_id not in self.session_histories:
            self.session_histories[session_id] = WritingSessionHistory(
                session_id
            )
        return self.session_histories[session_id]

    async def run(
        self, user_input: str, session_id: str, log_callback: Optional[Callable] = None
    ) -> dict:
        """运行多Agent协作流程"""
        session_id = (session_id or "").strip()
        if not session_id:
            raise ValueError("session_id 不能为空")

        safety_result = await check_input_security(user_input)
        if not safety_result.allowed:
            await emit_log(log_callback, "SafetyGuard", safety_result.reason)
            return safety_rejection_payload(safety_result)

        session_history = self.get_session_history(session_id)
        session_history.add_message(HumanMessage(content=user_input))

        await emit_log(log_callback, "Orchestrator", "开始智能任务编排...")

        context = ExecutionContext()
        plan = await self.plan_phase.run(
            user_input, session_history, context, log_callback
        )
        if plan.early_exit is not None:
            return plan.early_exit

        await self._execute_agent_pipeline(
            plan.pipeline_order, context, user_input, log_callback
        )

        if not content_agents_ran(context.executed_agents):
            context.mark_review_skipped()

        await self._run_review_repair_loop(context, user_input, log_callback)

        final_result = context.build_final_result()

        if context.review.failure_category != "policy_block":
            session_history.update_result(final_result)
        else:
            session_history.update_result({
                "title": "",
                "content": "",
                "hashtags": [],
                "image_url": "",
                "message": final_result.get("message", ""),
                "review_approved": False,
                "failure_category": "policy_block",
                "error_code": "POLICY_BLOCK",
            })
        session_history.update_plan(context.get_planning())

        await emit_log(log_callback, "Orchestrator", "多 Agent 协作完成，正在整理结果")

        return final_result

    async def _run_review_repair_loop(
        self,
        context: ExecutionContext,
        user_input: str,
        log_callback: Optional[Callable] = None,
    ) -> None:
        """审核未通过时同轮规则路由修复。"""
        if context.review.review_status != "failed":
            return

        deadline = time.monotonic() + settings.REVIEW_REPAIR_TOTAL_BUDGET_SECONDS
        max_rounds = settings.REVIEW_REPAIR_MAX_ROUNDS

        while (
            context.review.review_status == "failed"
            and context.review_repair_rounds < max_rounds
            and time.monotonic() < deadline
        ):
            repair_agents = route_review_failure(
                context.review.failure_category,
                context.review.feedback,
                context.review.corrections,
                context.partial_errors,
                context.image_repair_attempts,
            )
            if not repair_agents:
                break

            context.review_repair_rounds += 1
            from app.utils.display_labels import format_agent_pipeline

            repair_labels = format_agent_pipeline(repair_agents)
            await emit_log(
                log_callback,
                "Orchestrator",
                f"审核未通过，自动修复（第 {context.review_repair_rounds} 轮）：{' → '.join(repair_labels)}",
                intent="review_failure",
            )

            builder = AgentInputBuilder(context, user_input, repair_mode=True)
            await self._execute_agent_pipeline(
                repair_agents,
                context,
                user_input,
                log_callback,
                builder=builder,
            )

            if "ImageAgent" in repair_agents:
                context.image_repair_attempts += 1

            if context.review.review_status in (
                "passed",
                "policy_block",
                "error",
            ):
                break

    async def _execute_agent_pipeline(
        self,
        agent_names: List[str],
        context: ExecutionContext,
        user_input: str,
        log_callback: Optional[Callable] = None,
        builder: Optional[AgentInputBuilder] = None,
    ) -> None:
        """执行 Agent 流程"""
        if builder is None:
            builder = AgentInputBuilder(context, user_input)
        mapper = ResultMapper(context)

        for agent_name in agent_names:
            if agent_name not in self.agent_map:
                await emit_log(
                    log_callback, agent_name, f"未知 Agent: {agent_name}，跳过"
                )
                continue

            agent_input = builder.build(agent_name)

            try:
                result = await self.agent_executor.execute(
                    agent_name,
                    agent_input,
                    log_callback,
                    history=context.get_history_data(),
                )
            except Exception as e:
                if agent_name == "ImageAgent":
                    code = classify_agent_failure(e)
                    context.partial_errors["ImageAgent"] = code
                    await emit_log(
                        log_callback,
                        "ImageAgent",
                        "配图生成失败，已跳过并继续后续流程",
                    )
                    context.set_image(image_url="", prompt="")
                    context.record_agent_executed(agent_name)
                    continue
                raise

            context.record_agent_executed(agent_name)
            if result is not None:
                mapper.map_result(agent_name, result)
