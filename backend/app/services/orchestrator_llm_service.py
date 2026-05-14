from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from app.config import settings
from app.utils.llm_factory import llm_factory
from typing import Dict, List, Optional
from pydantic import BaseModel
from langchain_core.messages import BaseMessage


class RoutingDecision(BaseModel):
    """路由决策模型"""

    task_type: str
    agents_to_call: List[str]
    reasoning: str
    priority_order: List[str]

# 保留作扩展
class RetryDecision(BaseModel):
    """重试决策模型"""

    should_retry: bool
    action_type: str
    target_agent: Optional[str] = None
    modified_params: Optional[Dict] = None
    reasoning: str


class OrchestratorLLMService:
    """编排器LLM服务"""

    def __init__(self):
        """初始化编排器LLM服务"""
        # 初始化路由决策提示模板
        self.routing_prompt = PromptTemplate(
            template="""你是一个智能任务路由器，负责分析任务并决定调用哪些Agent。

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
            input_variables=["user_input", "planning_result", "intent_guidance", "intent", "format_instructions"],
        )

        # 初始化重试决策提示模板
        self.retry_prompt = PromptTemplate(
            template="""你是一个智能重试策略决策器，负责分析错误并决定最佳的重试策略。
可用的Agent：
1. PlannerAgent - 策划Agent
2. CopywriterAgent - 文案Agent
3. ImageAgent - 图片Agent
4. ReviewerAgent - 质检Agent

当前Agent：{current_agent}
错误信息：{error_info}
当前尝试次数：{attempt_count}
最大尝试次数：{max_attempts}

请分析错误并决定：
1. should_retry: 是否应该重试
2. action_type: 行动类型（retry_same_agent, switch_agent, modify_params, abort）
3. target_agent: 目标Agent（如果需要切换Agent）
4. modified_params: 修改的参数（如果需要修改参数）
5. reasoning: 决策理由

{format_instructions}

要求：
1. 如果错误是参数问题，尝试修改参数
2. 如果错误是Agent能力问题，切换到其他Agent
3. 如果尝试次数过多，考虑中止任务
4. 输出内容仅输出 JSON 对象，不要附加任何解释""",
            input_variables=["current_agent", "error_info", "attempt_count", "max_attempts", "format_instructions"],
        )

        # 初始化意图分析提示模板
        self.intent_prompt = PromptTemplate(
            template="""你是一个意图分析专家，负责分析用户的输入意图。

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

    async def route_task(
        self, user_input: str, planning_result: Dict, intent: str = "new_task"
    ) -> RoutingDecision:
        """动态路由决策

        Args:
            user_input: 用户输入
            planning_result: PlannerAgent 的输出字典
            intent: 用户意图类型

        Returns:
            路由决策
        """
        parser = JsonOutputParser(pydantic_object=RoutingDecision)

        intent_guidance = ""
        if intent == "new_task":
            intent_guidance = "用户开始一个新任务，需要完整的创作流程。"
        elif intent == "refine_content":
            intent_guidance = "用户要修改/优化现有内容（如修改文案、调整风格），应只调用CopywriterAgent（如需要可加 ReviewerAgent），避免重复规划。 "
        elif intent == "refine_image":
            intent_guidance = "用户想根据输入的要求重新生成图片信息，应只调用 ImageAgent（如需要可加 ReviewerAgent），不需要重新规划。"
        elif intent == "change_topic":
            intent_guidance = "用户更换了主题，需要重新规划并执行完整流程。"
        else:
            intent_guidance = "根据具体情况判断需要的 Agent。"

        input_data = {
            "user_input": user_input,
            "planning_result": str(planning_result),
            "intent": intent,
            "intent_guidance": intent_guidance,
        }

        try:
            result = await llm_factory.run_chain_with_dynamic_tokens(
                prompt_template=self.routing_prompt,
                chain_input=input_data,
                parser=parser,
                model_name=settings.BASE_MODEL,
                temperature=0.3,
            )
            return RoutingDecision(**result)
        except Exception as e:
            print(f"路由决策失败: {str(e)}")
            return RoutingDecision(
                task_type="new_task",
                agents_to_call=["CopywriterAgent", "ImageAgent", "ReviewerAgent"],
                reasoning="默认路由：执行完整的内容创作流程",
                priority_order=["CopywriterAgent", "ImageAgent", "ReviewerAgent"],
            )

    async def analyze_intent(
        self, user_input: str, chat_history: List[BaseMessage]
    ) -> str:
        """分析用户意图

        Args:
            user_input: 用户输入
            chat_history: 对话历史

        Returns:
            意图类型: new_task, refine_content, change_topic, etc.
        """
        try:
            print("开始识别意图")
            history_str = "\n".join(
                [f"{msg.type}: {msg.content}" for msg in chat_history]
            )
            input_data = {"user_input": user_input, "chat_history": history_str}

            result = await llm_factory.run_chain_with_dynamic_tokens(
                prompt_template=self.intent_prompt,
                chain_input=input_data,
                model_name=settings.BASE_MODEL,
                temperature=0.1,
            )

            print("完成识别意图")
            return str(result.content).strip()
        except Exception as e:
            print(f"意图识别失败: {str(e)}")
            return "new_task"
