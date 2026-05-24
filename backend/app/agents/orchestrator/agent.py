from app.agents.planner_agent import PlannerAgent
from app.agents.copywriter_agent import CopywriterAgent
from app.agents.image_agent import ImageAgent
from app.agents.reviewer_agent import ReviewerAgent
from app.agents.product_rag_system.agent import ProductRagAgent
from app.services.orchestrator_llm_service import (
    OrchestratorLLMService,
    IntentAnalysisTimeoutError,
)
from app.config import settings
from app.security.input_guard import check_input_security, safety_rejection_payload
from app.utils.retry_policy import classify_agent_failure
from app.utils.display_labels import format_agent_pipeline, intent_display_label
from app.utils.log_callback import emit_log
from .execution_context import ExecutionContext
from .agent_input_builder import AgentInputBuilder
from .agent_executor import AgentExecutor
from .result_mapper import ResultMapper
from typing import Optional, Callable, Dict, Any, List
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import BaseMessage, HumanMessage
from collections import deque
from dotenv import load_dotenv
import asyncio

load_dotenv()

FRESH_TASK_INTENTS = frozenset({"new_task", "change_topic"})


def is_fresh_task_intent(intent: str) -> bool:
    """新任务 / 换题：执行时不复用上一轮 plan 与 result。"""
    return intent in FRESH_TASK_INTENTS


class WritingSessionHistory(BaseChatMessageHistory):
    """内存存储"""

    def __init__(self, session_id: str, max_messages: int = 20):
        self.session_id = session_id
        self.messages: deque = deque(maxlen=max_messages)
        self._last_result: Optional[Dict[str, Any]] = None
        self._last_plan: Optional[Dict[str, Any]] = None

    def add_message(self, message: BaseMessage) -> None:
        """添加消息"""
        self.messages.append(message)

    def get_messages(self) -> List[BaseMessage]:
        """获取所有消息"""
        return list(self.messages)

    def clear(self) -> None:
        """清空会话"""
        self.messages.clear()
        self._last_result = None
        self._last_plan = None

    def get_last_result(self) -> Optional[Dict[str, Any]]:
        """获取最后的结果"""
        print(f"[DEBUG] get_last_result - 返回: {self._last_result}")
        return self._last_result

    def get_last_plan(self) -> Optional[Dict[str, Any]]:
        return self._last_plan

    def update_result(self, result: Dict[str, Any]) -> None:
        if result:
            self._last_result = result

    def update_plan(self, plan: Dict[str, Any]) -> None:
        if plan:
            self._last_plan = plan

class DialogOrchestratorAgent:
    """Agent协调器"""

    def __init__(self, session_timeout_seconds: int = 1800):
        """初始化协调器"""
        self.planner_agent = PlannerAgent()
        self.copywriter_agent = CopywriterAgent()
        self.image_agent = ImageAgent()
        self.reviewer_agent = ReviewerAgent()
        self.rag_agent = ProductRagAgent()
        self.llm_service = OrchestratorLLMService()

        # Agent映射表
        self.agent_map = {
            "PlannerAgent": self.planner_agent,
            "CopywriterAgent": self.copywriter_agent,
            "ImageAgent": self.image_agent,
            "ReviewerAgent": self.reviewer_agent,
            "RagAgent": self.rag_agent,
        }

        # Agent 执行器
        self.agent_executor = AgentExecutor(self.agent_map)

        # 会话历史存储
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
        """运行多Agent协作流程

        Args:
            user_input: 用户输入
            session_id: 会话ID
            log_callback: 日志回调函数

        Returns:
            最终结果
        """
        session_id = (session_id or "").strip()
        if not session_id:
            raise ValueError("session_id 不能为空")

        safety_result = await check_input_security(user_input)
        if not safety_result.allowed:
            await emit_log(log_callback, "SafetyGuard", safety_result.reason)
            return safety_rejection_payload(safety_result)

        # 获取会话历史
        session_history = self.get_session_history(session_id)
        session_history.add_message(HumanMessage(content=user_input))

        await emit_log(log_callback, "Orchestrator", "开始智能任务编排...")

        try:
            intent = await self.llm_service.analyze_intent(
                user_input, session_history.messages
            )
        except IntentAnalysisTimeoutError as e:
            await emit_log(log_callback, "Orchestrator", str(e))
            return e.to_early_exit()
        await emit_log(
            log_callback,
            "Orchestrator",
            f"识别为「{intent_display_label(intent)}」",
            intent=intent,
        )

        # 处理问答意图
        if intent == "ask_question":
            await emit_log(
                log_callback,
                "Orchestrator",
                "很抱歉，我无法回答您的问题，你可以换个问题，比如让我写商品的宣传文案",
                intent=intent,
            )
            return {
                "title": "",
                "content": "",
                "hashtags": [],
                "image_url": "",
                "message": "抱歉，我无法回答问题。这是一个小红书文案生成平台，请输入您想要生成的文案要求，例如：帮我写一篇关于防晒霜的推荐文案"
            }

        # 初始化执行上下文
        context = ExecutionContext()

        # 准备规划和历史数据
        await self._prepare_context(
            context, session_history, intent, user_input, log_callback
        )

        routing_decision = await self.llm_service.route_task(
            user_input, context.get_planning(), intent
        )
        pipeline_labels = format_agent_pipeline(routing_decision.priority_order)
        await emit_log(
            log_callback,
            "Orchestrator",
            f"接下来：{' → '.join(pipeline_labels)}",
        )

        # 执行 Agent 流程
        await self._execute_agent_pipeline(
            routing_decision.priority_order, context, user_input, log_callback
        )

        # 构建最终结果
        final_result = context.build_final_result()

        # 保存会话状态
        session_history.update_result(final_result)
        session_history.update_plan(context.get_planning())
        print(f"[DEBUG] save_history - last_plan: {session_history.get_last_plan()}")
        print(f"[DEBUG] save_history - last_result: {session_history.get_last_result()}")

        await emit_log(log_callback, "Orchestrator", "多 Agent 协作完成，正在整理结果")

        return final_result

    async def _prepare_context(
        self,
        context: ExecutionContext,
        session_history: WritingSessionHistory,
        intent: str,
        user_input: str,
        log_callback: Optional[Callable] = None,
    ) -> None:
        """准备执行上下文"""
        if is_fresh_task_intent(intent):
            planning_result = await asyncio.wait_for(
                self.planner_agent.run(
                    user_input, log_callback, history=""
                ),
                timeout=settings.AGENT_TIMEOUT_PLANNER_AGENT_SECONDS,
            )

            context.set_planning(planning_result)
            await emit_log(
                log_callback,
                "Orchestrator",
                "新任务/换题：已重新规划，不加载历史文案与图片",
            )
        else:
            last_plan = session_history.get_last_plan()
            print(f"使用历史规划：{last_plan}")
            if last_plan:
                context.load_from_dict({"planning": last_plan})
                await emit_log(log_callback, "Orchestrator", "使用历史计划")
            else:
                planning_result = await asyncio.wait_for(
                    self.planner_agent.run(
                        user_input, log_callback, history=""
                    ),
                    timeout=settings.AGENT_TIMEOUT_PLANNER_AGENT_SECONDS,
                )
                context.set_planning(planning_result)
                await emit_log(
                    log_callback, "Orchestrator", "未找到历史规划，已自动重建规划"
                )

        if not is_fresh_task_intent(intent):
            last_result = session_history.get_last_result()
            print(f"使用历史结果：{last_result}")
            if last_result:
                context.load_from_dict({
                    "copywriting": {
                        "title": last_result.get("title", ""),
                        "content": last_result.get("content", ""),
                        "hashtags": last_result.get("hashtags", []),
                    },
                    "image": {
                        "image_url": last_result.get("image_url", ""),
                        "prompt": last_result.get("prompt", last_result.get("image_prompt", "")),
                    },
                })

                context.set_last_result(last_result)
                await emit_log(log_callback, "Orchestrator", "加载上次生成的文案信息")


    async def _execute_agent_pipeline(
        self,
        agent_names: List[str],
        context: ExecutionContext,
        user_input: str,
        log_callback: Optional[Callable] = None,
    ) -> None:
        """执行 Agent 流程"""
        builder = AgentInputBuilder(context, user_input)
        mapper = ResultMapper(context)

        for agent_name in agent_names:
            if agent_name not in self.agent_map:
                await emit_log(
                    log_callback, agent_name, f"未知 Agent: {agent_name}，跳过"
                )
                continue

            # 构建输入
            agent_input = builder.build(agent_name)

            # 执行 Agent（ImageAgent 失败时部分成功：保留文案等，带 image_error_code）
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
                    continue
                raise

            # 映射结果到上下文
            if result is not None:
                mapper.map_result(agent_name, result)
