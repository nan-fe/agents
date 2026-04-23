from typing import Dict, Any, List, Optional
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser
from app.models.schemas import RoutingDecision, RetryDecision
from app.config import settings
from langchain_core.messages import BaseMessage


class OrchestratorLLMService:
    """协调器LLM服务"""
    
    def __init__(self):
        """初始化协调器LLM服务"""
        self.llm = ChatOpenAI(
            model_name=settings.SILICONFLOW_MODEL,
            temperature=0.3,
            api_key=settings.SILICONFLOW_API_KEY,
            base_url=settings.SILICONFLOW_BASE_URL
        )
        
        # 路由决策提示模板
        self.routing_template = """
        你是一位智能任务协调器，负责根据用户输入和策划结果决定调用哪些Agent以及调用顺序。
        
        用户输入：{user_input}
        
        策划结果：
        {planning_result}
        
        可用的Agent：
        - PlannerAgent：生成任务计划
        - CopywriterAgent：生成文案
        - ImageAgent：生成图片
        - ReviewerAgent：审核内容
        - RagAgent：获取商品信息
        
        请根据用户输入和策划结果，决定：
        1. 需要调用哪些Agent
        2. 调用顺序（优先级）
        3. 决策理由
        
        要求：
        1. 输出内容仅输出 JSON 对象，不要附加任何解释
        2. 请逐步思考每一步的决策过程
        """
        
        self.routing_prompt = PromptTemplate(
            template=self.routing_template,
            input_variables=["user_input", "planning_result"]
        )
        
        self.routing_parser = JsonOutputParser(pydantic_object=RoutingDecision)
        self.routing_chain = self.routing_prompt | self.llm | self.routing_parser
        
        # 重试决策提示模板
        self.retry_template = """
        你是一位智能任务协调器，负责根据错误信息决定重试策略。
        
        错误信息：{error_info}
        当前Agent：{current_agent}
        当前尝试次数：{attempt_count}
        最大尝试次数：{max_attempts}
        
        可用的Agent：
        - PlannerAgent：生成任务计划
        - CopywriterAgent：生成文案
        - ImageAgent：生成图片
        - ReviewerAgent：审核内容
        - RagAgent：获取商品信息
        
        请决定：
        1. 是否需要重试
        2. 行动类型（retry：重试当前Agent，switch_agent：切换到其他Agent，modify_params：修改参数）
        3. 如果切换Agent，请指定目标Agent
        4. 如果修改参数，请指定修改的参数
        5. 决策理由
        
        要求：
        1. 输出内容仅输出 JSON 对象，不要附加任何解释
        2. 请逐步思考每一步的决策过程
        """
        
        self.retry_prompt = PromptTemplate(
            template=self.retry_template,
            input_variables=["error_info", "current_agent", "attempt_count", "max_attempts"]
        )
        
        self.retry_parser = JsonOutputParser(pydantic_object=RetryDecision)
        self.retry_chain = self.retry_prompt | self.llm | self.retry_parser
        
        # 意图分析提示模板
        self.intent_template = """
        你是一位意图分析专家，负责分析用户输入的意图。
        
        用户输入：{user_input}
        
        对话历史：
        {conversation_history}
        
        请分析用户的意图，可能的意图包括：
        - new_task：创建新任务
        - refine_content：修改内容
        - change_style：改变风格
        - add_information：添加信息
        - other：其他意图
        
        要求：
        1. 直接输出意图类型，不要附加任何解释
        2. 请逐步思考每一步的分析过程
        """
        
        self.intent_prompt = PromptTemplate(
            template=self.intent_template,
            input_variables=["user_input", "conversation_history"]
        )
        
        self.intent_chain = self.intent_prompt | self.llm | StrOutputParser()
    
    async def route_task(self, user_input: str, planning_result: Dict[str, Any]) -> RoutingDecision:
        """路由任务
        
        Args:
            user_input: 用户输入
            planning_result: 策划结果
            
        Returns:
            路由决策
        """
        try:
            result = await self.routing_chain.ainvoke({
                "user_input": user_input,
                "planning_result": planning_result
            })
            return RoutingDecision(**result)
        except Exception as e:
            print("routing error", e)
            # 返回默认路由决策
            return RoutingDecision(
                agents_to_call=["PlannerAgent", "CopywriterAgent", "ImageAgent", "ReviewerAgent"],
                priority_order=["PlannerAgent", "CopywriterAgent", "ImageAgent", "ReviewerAgent"],
                reasoning="默认路由决策"
            )
    
    async def decide_retry_strategy(self, error_info: str, current_agent: str, attempt_count: int, max_attempts: int) -> RetryDecision:
        """决定重试策略
        
        Args:
            error_info: 错误信息
            current_agent: 当前Agent
            attempt_count: 当前尝试次数
            max_attempts: 最大尝试次数
            
        Returns:
            重试决策
        """
        try:
            result = await self.retry_chain.ainvoke({
                "error_info": error_info,
                "current_agent": current_agent,
                "attempt_count": attempt_count,
                "max_attempts": max_attempts
            })
            return RetryDecision(**result)
        except Exception as e:
            print("retry decision error", e)
            # 返回默认重试决策
            return RetryDecision(
                should_retry=attempt_count < max_attempts,
                action_type="retry",
                target_agent=None,
                modified_params=None,
                reasoning="默认重试策略"
            )
    
    async def analyze_intent(self, user_input: str, conversation_history: List[BaseMessage]) -> str:
        """分析用户意图
        
        Args:
            user_input: 用户输入
            conversation_history: 对话历史
            
        Returns:
            意图类型
        """
        try:
            # 构建对话历史字符串
            history_str = "\n".join([f"{msg.type}: {msg.content}" for msg in conversation_history])
            
            result = await self.intent_chain.ainvoke({
                "user_input": user_input,
                "conversation_history": history_str
            })
            
            # 清理结果
            result = result.strip().lower()
            return result
        except Exception as e:
            print("intent analysis error", e)
            return "new_task"


from langchain_core.output_parsers import StrOutputParser