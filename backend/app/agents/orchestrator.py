from app.agents.planner_agent import PlannerAgent
from app.agents.copywriter_agent import CopywriterAgent
from app.agents.image_agent import ImageAgent
from app.agents.reviewer_agent import ReviewerAgent
from app.agents.product_rag_agent import ProductRagAgent
from app.services.orchestrator_llm_service import OrchestratorLLMService
from typing import Optional, Callable
from app.models.schemas import PlanStep

class AgentOrchestrator:
    """Agent协调器"""
    
    def __init__(self):
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
            "RagAgent": self.rag_agent
        }
    
    async def run(self, user_input: str, log_callback: Optional[Callable] = None) -> dict:
        """运行多Agent协作流程
        
        Args:
            user_input: 用户输入
            log_callback: 日志回调函数
            
        Returns:
            最终结果
        """
        await log_callback("Orchestrator", "开始智能任务编排...")
        
        # ========== 阶段1：规划 ==========
        # 1.1 调用 PlannerAgent 生成任务计划（包含商品推荐和步骤列表）
        planning_result = await self.planner_agent.run(user_input, log_callback)
        await log_callback("Orchestrator", f"策划完成，主题: {planning_result.topic}")
        
        # ========== 阶段2：动态执行每个步骤 ==========
        # 2. LLM 动态路由决策（基于策划结果）
        routing_decision = await self.llm_service.route_task(
            user_input, 
            planning_result.model_dump()
        )
        await log_callback("Orchestrator", f"路由决策: 调用 {routing_decision.agents_to_call}, 顺序: {routing_decision.priority_order}")
        # 3. 准备执行上下文
        execution_context = {
            "planning": planning_result.model_dump(),
            "rag_context": None,      # 商品上下文（按需填充）
            "copywriting": None,
            "image": None,
            "review": None
        }
        # 4. 按优先级顺序执行 Agent
        for agent_name in routing_decision.priority_order:
            if agent_name not in self.agent_map:
                await log_callback("Orchestrator", f"未知 Agent: {agent_name}，跳过")
                continue
            
            # 特殊处理：如果当前是 CopywriterAgent 且 RAG 上下文尚未加载，则先调用 RagAgent
            if agent_name == "CopywriterAgent" and execution_context["rag_context"] is None:
                await log_callback("Orchestrator", "检测到需要生成文案，正在调用 RagAgent 获取商品上下文...")
                rag_result = await self._execute_with_retry(
                    self.rag_agent,
                    {"query": user_input, "planning": planning_result.model_dump()},
                    log_callback,
                    "RagAgent"
                )
                execution_context["rag_context"] = rag_result
                await log_callback("Orchestrator", "RAG 商品上下文已加载")
            
            # 构建当前 Agent 的输入
            agent_input = self._build_input_for_agent(
                agent_name, execution_context, user_input
            )
            print("agent_input",agent_name,agent_input)
            # 执行 Agent
            agent = self.agent_map[agent_name]
            result = await self._execute_with_retry(
                agent, agent_input, log_callback, agent_name
            )
            
            # 存储结果
            self._store_result_to_context(agent_name, result, execution_context)
            
            # 如果审核不通过，尝试修正（重新生成文案）
            if agent_name == "ReviewerAgent" and hasattr(result, "approved") and not result.approved:
                await self._handle_review_failure(execution_context, log_callback)
        # ========== 阶段3：整合最终结果 ==========
        final_result = self._build_final_result(execution_context)
        await log_callback("Orchestrator", "多Agent协作完成，生成最终结果")
        return final_result

    def _build_input_for_agent(self, agent_name: str, context: dict, user_input: str) -> any:
        """为不同 Agent 构建输入参数"""
        planning = context["planning"]
        if agent_name == "CopywriterAgent":
            print("context",context)
            enhanced = {
                "topic": planning.get("topic"),
                "target_audience": planning.get("target_audience"),
                "core_selling_points": planning.get("core_selling_points"),
                "tone_style": planning.get("tone_style"),
                "user_input": user_input,
                "product_context": context.get("rag_context")   # RAG 提供的商品信息
            }
            return enhanced
        
        elif agent_name == "ImageAgent":
            # 基于图片需求和已有的文案
            copywriting = context.get("copywriting") or {}
            
            return {
                "image_requirements": planning.get("image_requirements"),
                "copywriting_content": copywriting.get("content", ""),
                "topic": planning.get("topic"),
                "target_audience": planning.get("target_audience"),
                "core_selling_points": planning.get("core_selling_points"),
                "tone_style": planning.get("tone_style"),
                "product_category": planning.get("product_category")
            }
        
        elif agent_name == "ReviewerAgent":
            copywriting = context.get("copywriting") or {}
            image = context.get("image") or {}
            return {
                "copywriting_title": copywriting.get("title", ""),
                "copywriting_content": copywriting.get("content", ""),
                "copywriting_hashtags": copywriting.get("hashtags", []),
                "image_url": image.get("image_url", ""),
                "image_prompt": image.get("prompt", "")
            }
        
        elif agent_name == "RagAgent":
            return user_input
        
        else:
            # 默认返回规划结果
            return {}
    
    def _store_result_to_context(self, agent_name: str, result, context: dict):
        if agent_name == "CopywriterAgent":
            context["copywriting"] = {
                "title": getattr(result, "title", ""),
                "content": getattr(result, "content", ""),
                "hashtags": getattr(result, "hashtags", [])
            }
        elif agent_name == "ImageAgent":
            context["image"] = {
                "image_url": getattr(result, "image_url", ""),
                "prompt": getattr(result, "prompt", "")
            }
        elif agent_name == "ReviewerAgent":
            context["review"] = {
                "approved": getattr(result, "approved", False),
                "feedback": getattr(result, "feedback", "")
            }
        elif agent_name == "RagAgent":
            context["rag_context"] = result
    
    async def _execute_with_retry(
        self,
        agent,
        input_data,
        log_callback: Optional[Callable],
        agent_name: str,
        max_attempts: int = 3
    ):
        """执行Agent并支持自适应重试
        
        Args:
            agent: Agent实例
            input_data: 输入数据
            log_callback: 日志回调
            agent_name: Agent名称
            max_attempts: 最大尝试次数
            
        Returns:
            执行结果
        """
        attempt_count = 0
        last_error = None
        
        while attempt_count < max_attempts:
            attempt_count += 1
            try:
                await log_callback("Orchestrator", f"执行 {agent_name}，第 {attempt_count} 次尝试,{input_data}")
                print(f"执行 {agent_name}，第 {attempt_count} 次尝试,{input_data}")
                result = await agent.run(input_data)
                await log_callback("Orchestrator", f"{agent_name} 执行成功")
                return result
            except Exception as e:
                last_error = str(e)
                await log_callback("Orchestrator", f"{agent_name} 执行失败: {last_error}")
                print("last_error",agent_name,last_error)
                
                # 使用LLM决定重试策略
                retry_decision = await self.llm_service.decide_retry_strategy(
                    error_info=last_error,
                    current_agent=agent_name,
                    attempt_count=attempt_count,
                    max_attempts=max_attempts
                )
                
                await log_callback("Orchestrator", f"重试决策: {retry_decision.action_type}, 理由: {retry_decision.reasoning}")
                
                if not retry_decision.should_retry:
                    await log_callback("Orchestrator", f"中止重试，返回默认结果")
                    break
                
                # 根据决策调整策略
                if retry_decision.action_type == "switch_agent":
                    # 切换到其他Agent
                    target_agent_name = retry_decision.target_agent
                    if target_agent_name and target_agent_name in self.agent_map:
                        agent = self.agent_map[target_agent_name]
                        agent_name = target_agent_name
                        await log_callback("Orchestrator", f"切换到 {target_agent_name}")
                elif retry_decision.action_type == "modify_params":
                    # 修改参数
                    if retry_decision.modified_params:
                        input_data = self._merge_params(input_data, retry_decision.modified_params)
                        await log_callback("Orchestrator", f"修改参数: {retry_decision.modified_params}")
        
        # 返回默认结果
        await log_callback("Orchestrator", f"{agent_name} 所有尝试失败，返回默认结果")
        return self._get_default_result(agent_name)
    
    async def _handle_review_failure(self, context: dict, log_callback: Callable):
        """处理审核失败
        
        Args:
            review_result: 审核结果
            planning_result: 策划结果
            log_callback: 日志回调
        """
        review = context.get("review", {})
        await log_callback("Orchestrator", f"审核未通过: {review.get('feedback')}")
        
        # 使用 LLM 决定修正策略（可复用原有 decide_retry_strategy）
        retry_decision = await self.llm_service.decide_retry_strategy(
            error_info=review.get("feedback", "审核未通过"),
            current_agent="ReviewerAgent",
            attempt_count=1,
            max_attempts=3
        )
        
        if retry_decision.action_type == "modify_params" and retry_decision.modified_params:
            # 重新生成文案
            enhanced = context["planning"].copy()
            enhanced.update(retry_decision.modified_params)
            if context.get("rag_context"):
                enhanced["product_context"] = context["rag_context"]
            new_copy = await self._execute_with_retry(
                self.copywriter_agent, enhanced, log_callback, "CopywriterAgent"
            )
            self._store_result_to_context("CopywriterAgent", new_copy, context)
            
    def _merge_params(self, original_params: dict, new_params: dict) -> dict:
        """合并参数
        
        Args:
            original_params: 原始参数
            new_params: 新参数
            
        Returns:
            合并后的参数
        """
        merged = original_params.copy()
        merged.update(new_params)
        return merged
    
    def _get_default_result(self, agent_name: str):
        """获取Agent的默认结果
        
        Args:
            agent_name: Agent名称
            
        Returns:
            默认结果
        """
        from app.models.schemas import CopywritingResult, ImageResult, ReviewResult
        
        if agent_name == "CopywriterAgent":
            return CopywritingResult(
                title="默认标题",
                content="默认内容",
                hashtags=["#小红书", "#推荐"]
            )
        elif agent_name == "ImageAgent":
            return ImageResult(
                image_url="https://via.placeholder.com/800x600",
                prompt="默认图片"
            )
        elif agent_name == "ReviewerAgent":
            return ReviewResult(
                approved=True,
                feedback="默认通过"
            )
        else:
            return None
    
    def _build_final_result(self, context: dict) -> dict:
        """从上下文中提取最终结果"""
        copy = context.get("copywriting", {})
        image = context.get("image", {})
        plan = context.get("planning", {})
        
        final = {
            "title": copy.get("title", "默认标题"),
            "content": copy.get("content", "默认内容"),
            "hashtags": copy.get("hashtags", ["#小红书", "#推荐"]),
            "image_url": image.get("image_url", "https://via.placeholder.com/800x600"),
        }
        # 添加商品推荐
        if plan.get("product_recommendations"):
            final["product_recommendations"] = plan["product_recommendations"]
        return final