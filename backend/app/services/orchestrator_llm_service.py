from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser
from app.config import settings
from typing import Dict, List, Optional
from pydantic import BaseModel


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
            model_name="THUDM/GLM-4.1V-9B-Thinking",
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
        1. RagAgent - 商品信息RagAgent，检索本地数据库中相似的商品，拿到商品信息给文案 Agent 补充商品信息上下文
        2. CopywriterAgent - 文案Agent，生成小红书风格文案
        3. ImageAgent - 图片Agent，生成配图
        4. ReviewerAgent - 质检Agent，检查文案和图片是否合规
        
        用户输入：{user_input}
        策划结果：{planning_result}
        
        请分析任务类型并决定：
        1. task_type: 任务类型（product_recommendation, content_creation, image_generation, quality_check等）
        2. agents_to_call: 需要调用的Agent列表
        3. reasoning: 路由决策的理由
        4. priority_order: Agent调用的优先级顺序
        
        {format_instructions}
        
        要求：
        1. 根据任务复杂度和需求选择合适的Agent组合
        2. 考虑任务依赖关系，确定合理的调用顺序，比如文案agent调用前，需要调用rag agent 提供商品的上下文
        3. 如果任务简单，可以跳过某些Agent
        4. 大多数情况下都需要 ReviewerAgent 进行质量检查，除非任务极简单。
        5. agents_to_call 和 priority_order 必须从可用 Agent 中选择，且顺序合理。
        6. 输出内容仅输出 JSON 对象，不要附加任何解释
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
    
    async def decide_agent_for_step(
        self,
        step_description: str,
        available_agents: List[str],
        context_summary: str,
        step_input_overrides: Optional[Dict] = None
    ) -> AgentDecision:
        """为单个步骤动态决定使用哪个 Agent
        
        Args:
            step_description: 步骤描述
            available_agents: 可用的 Agent 名称列表
            context_summary: 当前执行上下文的摘要
            step_input_overrides: 步骤可能携带的输入覆盖（可选）
            
        Returns:
            AgentDecision: 包含选中的 Agent 和理由
        """
        parser = JsonOutputParser(pydantic_object=AgentDecision)
        
        template = """
        你是一个智能 Agent 路由器，负责为给定的任务步骤选择最合适的 Agent。
        
        可用 Agent 列表：{available_agents}
        当前步骤描述：{step_description}
        已有上下文摘要：{context_summary}
        {input_overrides_info}
        
        请根据步骤的需求和当前上下文，从可用 Agent 中选择一个最合适的。
        考虑因素：
        - 步骤描述中明确需要的能力（文案生成、图片生成、审核等）
        - 上下文是否已经产生了某些结果（例如已有文案则不需要再调用文案 Agent）
        - 任务依赖关系
        
        {format_instructions}
        
        要求：
        1. 只输出 JSON 对象，不要附加任何解释
        2. selected_agent 必须来自 available_agents 列表
        3. 如果无法决定，选择最通用的 Agent（如 CopywriterAgent）
        """
        
        input_overrides_info = ""
        if step_input_overrides:
            input_overrides_info = f"步骤输入覆盖：{step_input_overrides}"
        
        prompt = PromptTemplate(
            template=template,
            input_variables=["step_description", "available_agents", "context_summary"],
            partial_variables={
                "format_instructions": parser.get_format_instructions(),
                "input_overrides_info": input_overrides_info
            }
        )
        
        chain = prompt | self.llm | parser
        
        try:
            result = await chain.ainvoke({
                "step_description": step_description,
                "available_agents": ", ".join(available_agents),
                "context_summary": context_summary
            })
            return AgentDecision(**result)
        except Exception as e:
            # 默认决策：选择 CopywriterAgent（最通用的）
            return AgentDecision(
                selected_agent="CopywriterAgent",
                reasoning=f"LLM 决策失败，使用默认 Agent。错误: {str(e)}"
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
    
    async def fuse_and_summarize_information(
        self,
        planning_result: Dict,
        product_recommendations: List[Dict],
        previous_results: Optional[List[Dict]] = None
    ) -> InformationSummary:
        """信息融合与摘要
        
        Args:
            planning_result: 策划结果
            product_recommendations: 商品推荐
            previous_results: 之前的执行结果
            
        Returns:
            信息摘要
        """
        parser = JsonOutputParser(pydantic_object=InformationSummary)
        
        template = """
        你是一个信息融合专家，负责整合多个来源的信息并生成摘要。
        
        策划结果：{planning_result}
        商品推荐：{product_recommendations}
        之前的执行结果：{previous_results}
        
        请分析并提取：
        1. key_points: 关键要点（3-5个）
        2. product_insights: 商品洞察（2-3个）
        3. audience_insights: 受众洞察（2-3个）
        4. style_recommendations: 风格建议（2-3个）
        5. summary_text: 综合摘要（一段话）
        
        {format_instructions}
        
        要求：
        1. 提取最有价值的信息
        2. 识别关键卖点和特色
        3. 理解目标受众需求
        4. 提供风格和语气建议
        5. 输出内容仅输出 JSON 对象，不要附加任何解释
        """
        
        prompt = PromptTemplate(
            template=template,
            input_variables=["planning_result", "product_recommendations", "previous_results"],
            partial_variables={"format_instructions": parser.get_format_instructions()}
        )
        
        chain = prompt | self.llm | parser
        
        try:
            result = await chain.ainvoke({
                "planning_result": str(planning_result),
                "product_recommendations": str(product_recommendations),
                "previous_results": str(previous_results) if previous_results else "无"
            })
            return InformationSummary(**result)
        except Exception as e:
            # 默认信息摘要
            return InformationSummary(
                key_points=["质量好", "价格实惠", "使用方便"],
                product_insights=["适合目标人群", "性价比高"],
                audience_insights=["追求品质", "注重性价比"],
                style_recommendations=["亲切自然", "真实可信"],
                summary_text="这是一个适合目标人群的高性价比产品，建议采用亲切自然的风格进行推荐。"
            )
