"""编排层 LLM：意图识别、动态路由；超时用 wait_for，HTTP 重试交给 llm_factory。"""

import asyncio
from typing import Any, Dict, List, Optional

from langchain_core.messages import BaseMessage
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel

from app.config import settings
from app.security.prompt_rules import INTENT_SECURITY_PROMPT, ROUTING_SECURITY_PROMPT
from app.utils.llm_factory import llm_factory


class RoutingDecision(BaseModel):
    task_type: str
    agents_to_call: List[str]
    reasoning: str
    priority_order: List[str]


class IntentAnalysisTimeoutError(Exception):
    """意图 wait_for 超时；编排器捕获后 early return。"""

    def __init__(self, timeout_seconds: float):
        self.timeout_seconds = timeout_seconds
        super().__init__(
            f"意图分析超时（>{timeout_seconds}s），请稍后重试或简化输入"
        )

    def to_early_exit(self) -> Dict[str, Any]:
        return {
            "title": "",
            "content": "",
            "hashtags": [],
            "image_url": "",
            "message": "意图分析超时，请稍后重试或简化输入。",
            "error_code": "INTENT_TIMEOUT",
        }


def _default_route(reason: str) -> RoutingDecision:
    return RoutingDecision(
        task_type="new_task",
        agents_to_call=["CopywriterAgent", "ImageAgent", "ReviewerAgent"],
        reasoning=reason,
        priority_order=["CopywriterAgent", "ImageAgent", "ReviewerAgent"],
    )


def _routing_intent_guidance(intent: str) -> str:
    # 与历史版本保持一致的提示文案，避免路由模型行为漂移
    if intent == "new_task":
        return "用户开始一个新任务，需要完整的创作流程。"
    if intent == "refine_content":
        return (
            "用户要修改/优化现有内容（如修改文案、调整风格），应只调用CopywriterAgent"
            "（如需要可加 ReviewerAgent），避免重复规划。 "
        )
    if intent == "refine_image":
        return (
            "用户想根据输入的要求重新生成图片信息，应只调用 ImageAgent"
            "（如需要可加 ReviewerAgent），不需要重新规划。"
        )
    if intent == "change_topic":
        return "用户更换了主题，需要重新规划并执行完整流程。"
    return "根据具体情况判断需要的 Agent。"


class OrchestratorLLMService:
    """编排器 LLM：意图、路由。"""

    def __init__(self):
        self.routing_prompt = PromptTemplate(
            template="""你是一个智能任务路由器，负责分析任务并决定调用哪些Agent。
"""
            + ROUTING_SECURITY_PROMPT
            + """
可用的Agent：
1. RagAgent - 商品信息 RagAgent，检索本地数据库中相似的商品，拿到商品信息
2. CopywriterAgent - 文案 Agent，负责生成或者修改小红书风格文案
3. ImageAgent - 图片 Agent，生成配图，如果之前已经生成过，且没有提及需要生成或者修改，则不会使用
4. ReviewerAgent - 质检 Agent，检查文案和图片是否合规

用户输入：{user_input}
策划结果：{planning_result}

用户意图分析：{intent_guidance}
意图类型：{intent}

请分析任务类型并决定：
1. task_type: 任务类型（product_recommendation, content_creation, image_generation, quality_check等）
2. agents_to_call: 需要调用的 Agent 列表
3. reasoning: 路由决策的理由
4. priority_order: Agent调用的优先级顺序

{format_instructions}

要求：
1. 根据用户意图选择合适的 Agent 组合：
   - new_task：需要完整流程，调用多个 Agent
   - refine_content：只调用CopywriterAgent，不需要重新规划和生图
   - refine_image：只调用 ImageAgent，不需要重新规划和写文案
   - change_topic：需要完整流程
2. 考虑任务依赖关系，确定合理的调用顺序，比如 RagAgent 在商品类型没有发生改变，则只在首次使用，使用的数据可以给文案 Agent 补充商品信息上下文。
3. 如果任务简单，可以跳过某些 Agent，比如简单的任务不需要调用 RagAgent或者其他 agent。
4. 大多数情况下都需要 ReviewerAgent 进行质量检查，除非任务极简单。
5. agents_to_call 和 priority_order 必须从可用 Agent 中选择，且顺序合理。
6. 输出内容仅输出 JSON 对象，不要附加任何解释""",
            input_variables=[
                "user_input",
                "planning_result",
                "intent_guidance",
                "intent",
                "format_instructions",
            ],
        )

        self.intent_prompt = PromptTemplate(
            template="""你是一个意图分析专家，负责分析用户的输入意图。
"""
            + INTENT_SECURITY_PROMPT
            + """
对话历史：{chat_history}
用户当前输入：{user_input}

请分析用户的意图，并返回以下类型之一：
1. new_task: 开始一个新的任务
2. refine_content: 优化或修改现有文案内容（如修改语气、风格、内容）
3. refine_image: 根据要求重新生成或修改图片（如更换背景、调整风格、修改构图）
4. change_topic: 更改主题
5. ask_question: 询问问题（有疑问句）

要求：
1. 仅返回意图类型，不输出任何解释
2. 基于用户输入和对话历史进行综合判断
3. 如果用户提到图片相关关键词（如换图、重新生成图片、修改图片），优先判断为 refine_image
4. 如果用户提到主题相关关键词（如改题、修改主题、更改主题），优先判断为 change_topic
5. 如果用户提到补充/添加/增加相关关键词（如补充内容、添加图片、增加元素），优先判断为 refine_content""",
            input_variables=["user_input", "chat_history"],
        )

    def _llm_orch_kwargs(self, temperature: float) -> Dict[str, Any]:
        """编排侧调大模型：模型名 + 编排专用 HTTP 重试次数（与全局 LLM 重试区分）。"""
        return {
            "model_name": settings.BASE_MODEL,
            "temperature": temperature,
            "http_retry_max_attempts": settings.LLM_ORCHESTRATION_HTTP_RETRY_MAX_ATTEMPTS,
        }

    async def route_task(
        self, user_input: str, planning_result: Dict, intent: str = "new_task"
    ) -> RoutingDecision:
        """动态路由；超时或其它失败 → 默认流水线。"""
        parser = JsonOutputParser(pydantic_object=RoutingDecision)
        timeout = settings.AGENT_TIMEOUT_ROUTING_SECONDS

        async def _call():
            raw = await llm_factory.run_chain_with_dynamic_tokens(
                prompt_template=self.routing_prompt,
                chain_input={
                    "user_input": user_input,
                    "planning_result": str(planning_result),
                    "intent": intent,
                    "intent_guidance": _routing_intent_guidance(intent),
                },
                parser=parser,
                **self._llm_orch_kwargs(0.3),
            )
            return RoutingDecision(**raw)

        try:
            return await asyncio.wait_for(_call(), timeout=timeout)
        except asyncio.TimeoutError:
            print(f"路由决策超时（>{timeout}s），使用默认流水线")
            return _default_route(f"路由超时（>{timeout}s）：默认完整创作流程")
        except Exception as e:
            print(f"路由决策失败: {e}")
            return _default_route("默认路由：执行完整的内容创作流程")

    async def analyze_intent(
        self, user_input: str, chat_history: List[BaseMessage]
    ) -> str:
        """意图识别；超时抛 IntentAnalysisTimeoutError，其它失败 → new_task。"""
        timeout = settings.AGENT_TIMEOUT_INTENT_SECONDS
        history_str = "\n".join(f"{m.type}: {m.content}" for m in chat_history)

        async def _call():
            r = await llm_factory.run_chain_with_dynamic_tokens(
                prompt_template=self.intent_prompt,
                chain_input={"user_input": user_input, "chat_history": history_str},
                **self._llm_orch_kwargs(0.1),
            )
            return str(r.content).strip()

        try:
            print("开始识别意图")
            intent = await asyncio.wait_for(_call(), timeout=timeout)
            print("完成识别意图")
            return intent
        except asyncio.TimeoutError as e:
            raise IntentAnalysisTimeoutError(timeout) from e
        except Exception as e:
            print(f"意图识别失败: {e}")
            return "new_task"
