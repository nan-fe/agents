from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser
from app.config import settings
from typing import Dict, List, Optional
from pydantic import BaseModel
from langchain_core.messages import BaseMessage


class RoutingDecision(BaseModel):
    """路由决策模型"""
    task_type: str
    agents_to_call: List[str]
    reasoning: str
    priority_order: List[str]

class AgentDecision(BaseModel):
    """单个步骤的 Agent 决策结果"""
    selected_agent: str   # 选中的 Agent 名称
    reasoning: str        # 决策理由

class RetryDecision(BaseModel):
    """重试决策模型"""
    should_retry: bool
    action_type: str
    target_agent: Optional[str] = None
    modified_params: Optional[Dict] = None
    reasoning: str


class InformationSummary(BaseModel):
    """信息摘要模型"""
    key_points: List[str]
    product_insights: List[str]
    audience_insights: List[str]
    style_recommendations: List[str]
    summary_text: str


class OrchestratorLLMService:
    """编排器LLM服务"""
    
    def __init__(self):
        """初始化编排器LLM服务"""
        self.llm = ChatOpenAI(
            model_name= settings.PLAN_MODEL,
            temperature=0.3,
            api_key=settings.SILICONFLOW_API_KEY,
            base_url=settings.SILICONFLOW_BASE_URL
        )
    
    async def route_task(self, user_input: str, planning_result: Dict) -> RoutingDecision:
        """动态路由决策
        
        Args:
            user_input: 用户输入
            planning_result: PlannerAgent 的输出字典，应包含以下字段：
              - topic: str
                - target_audience: List[str]
                - core_selling_points: List[str]
                - tone_style: str
                - image_requirements: str
                可能还有其他字段
            
        Returns:
            路由决策
        """
        parser = JsonOutputParser(pydantic_object=RoutingDecision)
        
        template = """
        你是一个智能任务路由器，负责分析任务并决定调用哪些Agent。
        
        可用的Agent：
        1. RagAgent - 商品信息 RagAgent，检索本地数据库中相似的商品，拿到商品信息
        2. CopywriterAgent - 文案 Agent，负责生成或者修改小红书风格文案
        3. ImageAgent - 图片 Agent，生成配图，如果之前已经生成过，且没有提及需要生成或者修改，则不会使用
        4. ReviewerAgent - 质检 Agent，检查文案和图片是否合规
        
        用户输入：{user_input}
        策划结果：{planning_result}
        
        请分析任务类型并决定：
        1. task_type: 任务类型（product_recommendation, content_creation, image_generation, quality_check等）
        2. agents_to_call: 需要调用的 Agent 列表
        3. reasoning: 路由决策的理由
        4. priority_order: Agent调用的优先级顺序
        
        {format_instructions}
        
        要求：
        1. 根据任务复杂度和需求选择合适的 Agent 组合
        2. 考虑任务依赖关系，确定合理的调用顺序，比如 RagAgent 在商品类型没有发生改变，则只在首次使用，使用的数据可以给文案 Agent 补充商品信息上下文。
        3. 如果任务简单，可以跳过某些 Agent
        4. 大多数情况下都需要 ReviewerAgent 进行质量检查，除非任务极简单。
        5. agents_to_call 和 priority_order 必须从可用 Agent 中选择，且顺序合理。
        6. 输出内容仅输出 JSON 对象，不要附加任何解释
        7. 调用规划与修改分析器，分析用户意图：
            修改类型：风格调整 + 内容补充。
            需要修改的段落：全文语气 + 在适当位置插入折扣信息。
        """
        
        prompt = PromptTemplate(
            template=template,
            input_variables=["user_input", "planning_result"],
            partial_variables={"format_instructions": parser.get_format_instructions()}
        )
        
        chain = prompt | self.llm | parser
        
        try:
            result = await chain.ainvoke({
                "user_input": user_input,
                "planning_result": str(planning_result)
            })
            return RoutingDecision(**result)
        except Exception as e:
            # 默认路由决策
            return RoutingDecision(
                task_type="content_creation",
                agents_to_call=["CopywriterAgent", "ImageAgent", "ReviewerAgent"],
                reasoning="默认路由：执行完整的内容创作流程",
                priority_order=["CopywriterAgent", "ImageAgent", "ReviewerAgent"]
            )
    

    async def decide_retry_strategy(
        self, 
        error_info: str, 
        current_agent: str,
        attempt_count: int,
        max_attempts: int = 3
    ) -> RetryDecision:
        """自适应重试策略
        
        Args:
            error_info: 错误信息
            current_agent: 当前Agent
            attempt_count: 当前尝试次数
            max_attempts: 最大尝试次数
            
        Returns:
            重试决策
        """
        parser = JsonOutputParser(pydantic_object=RetryDecision)
        
        template = """
        你是一个智能重试策略决策器，负责分析错误并决定最佳的重试策略。
        
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
        4. 输出内容仅输出 JSON 对象，不要附加任何解释
        """
        
        prompt = PromptTemplate(
            template=template,
            input_variables=["current_agent", "error_info", "attempt_count", "max_attempts"],
            partial_variables={"format_instructions": parser.get_format_instructions()}
        )
        
        chain = prompt | self.llm | parser
        
        try:
            result = await chain.ainvoke({
                "current_agent": current_agent,
                "error_info": error_info,
                "attempt_count": attempt_count,
                "max_attempts": max_attempts
            })
            return RetryDecision(**result)
        except Exception as e:
            # 默认重试决策
            if attempt_count >= max_attempts:
                return RetryDecision(
                    should_retry=False,
                    action_type="abort",
                    reasoning=f"已达到最大尝试次数{max_attempts}，中止任务"
                )
            else:
                return RetryDecision(
                    should_retry=True,
                    action_type="retry_same_agent",
                    reasoning="默认策略：重试当前Agent"
                )
     
    async def analyze_intent(self, user_input: str, chat_history: List[BaseMessage]) -> str:
        """分析用户意图
        
        Args:
            user_input: 用户输入
            chat_history: 对话历史
            
        Returns:
            意图类型：new_task, refine_content, change_topic, etc.
        """
        template = """
        你是一个意图分析专家，负责分析用户的输入意图。
        
        对话历史：{chat_history}
        用户当前输入：{user_input}
        
        请分析用户的意图，并返回以下类型之一：
        1. new_task: 开始一个新的任务
        2. refine_content: 优化或修改现有内容
        3. change_topic: 更改主题
        4. ask_question: 询问问题
        5. other: 其他意图
        
        要求：
        1. 仅返回意图类型，不输出任何解释
        2. 基于用户输入和对话历史进行综合判断
        """
        
        prompt = PromptTemplate(
            template=template,
            input_variables=["user_input", "chat_history"]
        )
        self.intent_llm = ChatOpenAI(
            model_name= settings.INTENT_MODEL,
            temperature=0.3,
            api_key=settings.SILICONFLOW_API_KEY,
            base_url=settings.SILICONFLOW_BASE_URL
        )
        
        chain = prompt | self.intent_llm
        
        try:
            print("开始识别意图")
            history_str = "\n".join([f"{msg.type}: {msg.content}" for msg in chat_history])
            result = await chain.ainvoke({
                "user_input": user_input,
                "chat_history": history_str
            })
            print("完成识别意图")

            return result.content.strip()
        except Exception as e:
            # 默认意图：新任务
            return "new_task"
