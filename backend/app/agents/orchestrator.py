from app.agents.planner_agent import PlannerAgent
from app.agents.copywriter_agent import CopywriterAgent
from app.agents.image_agent import ImageAgent
from app.agents.reviewer_agent import ReviewerAgent
from app.agents.product_rag_system.agent import ProductRagAgent
from app.services.orchestrator_llm_service import OrchestratorLLMService
from typing import Optional, Callable, Dict, Any, List
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import BaseMessage,AIMessage,HumanMessage
from collections import deque
from dotenv import load_dotenv

load_dotenv()


class WritingSessionHistory(BaseChatMessageHistory):
    """内存存储"""
    def __init__(self, session_id: str, max_messages: int = 20):
        self.session_id = session_id
        # 使用 deque 限制消息数量，自动淘汰旧消息
        self.messages: deque = deque(maxlen=max_messages)
        # 只保留最新结果
        self.current_result: Optional[Dict[str, Any]] = None
        self.last_plan: Optional[Dict[str, Any]] = None
    
    def add_message(self, message: BaseMessage) -> None:
        """添加消息，自动维护最大长度"""
        self.messages.append(message)
    
    def get_messages(self) -> List[BaseMessage]:
        """获取所有消息"""
        return list[Any](self.messages)
    
    def clear(self) -> None:
        """清空会话"""
        self.messages.clear()
        self.current_result = None
        self.last_plan = None
    
    def update_result(self, result: Dict[str, Any]) -> None:
        """更新最新结果"""
        self.current_result = result
    
    def get_last_result(self) -> Optional[Dict[str, Any]]:
        """获取最新结果"""
        return self.current_result
    
    def update_plan(self, plan: Dict[str, Any]) -> None:
        """更新计划"""
        self.last_plan = plan

class DialogOrchestratorAgent:
    """Agent协调器"""

    def __init__(self,session_timeout_seconds: int = 1800):
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

        # 会话历史存储
        self.session_histories: Dict[str, WritingSessionHistory] = {}
    
    def get_session_history(self, session_id: str) -> WritingSessionHistory:
        if session_id not in self.session_histories:
            self.session_histories[session_id] = WritingSessionHistory(session_id)
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
        # 获取会话历史
        session_history = self.get_session_history(session_id)
        # 将用户消息添加到历史
        session_history.add_message(HumanMessage(content=user_input))

        await log_callback("Orchestrator", "开始智能任务编排...")

        # 分析用户意图和会话历史
        intent = await self.llm_service.analyze_intent(
            user_input, session_history.messages
        )
        await log_callback("Orchestrator", f"用户意图分析: {intent}")

        if intent == "ask_question":
            # 询问问题 提前结束
            await log_callback(
                "Orchestrator", f"很抱歉，我无法回答您的问题，你可以换个问题，比如让我写商品的宣传文案"
            )
            return {
                "title": "",
                "content": "",
                "hashtags": [],
                "image_url": "",
                "message": "抱歉，我无法回答问题。这是一个小红书文案生成平台，请输入您想要生成的文案要求，例如：帮我写一篇关于防晒霜的推荐文案",
            }

        # 准备执行上下文
        execution_context = {
            "planning": session_history.last_plan or {},
            "rag_context": None,  # 商品上下文（按需填充）
            "copywriting": {},
            "image": {},
            "review": None,
        }
        history_data = ""
        # 动态决策：是否需要重新规划
        if intent == "new_task" or not session_history.last_plan:
            # 生成新的任务计划
            planning_result = await self.planner_agent.run(
                user_input, log_callback, history=history_data
            )
            await log_callback(
                "Orchestrator", f"策划完成，主题: {planning_result.topic}"
            )
            execution_context["planning"] = planning_result.model_dump()
            session_history.update_plan(execution_context["planning"])
        else:
            # 准备历史数据
            last_final_result = session_history.get_last_result()
            print("last_final_result", last_final_result)
            # 使用历史计划
            await log_callback("Orchestrator", "使用历史计划")
            print("历史计划", session_history.last_plan, execution_context["planning"])

            # 如果不是新任务，读取上次的FinalResult信息到执行上下文
            if last_final_result:
                history_data = f"上次生成的文案信息：\n标题：{last_final_result.get('title', '')}\n内容：{last_final_result.get('content', '')}\n标签：{', '.join(last_final_result.get('hashtags', []))}\n图片：{last_final_result.get('image_url', '')}\n图片提示：{last_final_result.get('image_prompt', '')}"
                print("准备历史数据完成", history_data)
                await log_callback("Orchestrator", "加载上次生成的文案信息")
                execution_context["copywriting"] = {
                    "title": last_final_result.get("title", ""),
                    "content": last_final_result.get("content", ""),
                    "hashtags": last_final_result.get("hashtags", []),
                }
                execution_context["image"] = {
                    "image_url": last_final_result.get("image_url", ""),
                    "image_prompt": last_final_result.get("image_prompt", ""),
                }

        print("LLM 动态路由决策，开始.....")
        # LLM 动态路由决策（传入意图识别结果）
        routing_decision = await self.llm_service.route_task(
            user_input, execution_context["planning"], intent
        )
        await log_callback(
            "Orchestrator",
            f"路由决策: 调用 {routing_decision.agents_to_call}",
        )

        # 按优先级顺序执行 Agent
        for agent_name in routing_decision.priority_order:
            if agent_name not in self.agent_map:
                await log_callback("Orchestrator", f"未知 Agent: {agent_name}，跳过")
                continue

            # 构建当前 Agent 的输入
            agent_input = self._build_input_for_agent(
                agent_name, execution_context, user_input
            )
            print("agent_input", agent_name, agent_input)
            # 执行 Agent
            agent = self.agent_map[agent_name]
            result = await self._execute_agent(
                agent, agent_input, log_callback, agent_name, history=history_data
            )

            # 存储结果
            self._store_result_to_context(agent_name, result, execution_context)

        # 整合最终结果
        final_result = self._build_final_result(execution_context)

        await log_callback("Orchestrator", "多Agent协作完成，生成最终结果")
        # 将 AI 回复添加到历史
        session_history.add_message(AIMessage(content=final_result.get('content', '')))
        
        # 保存最新结果
        session_history.update_result(final_result)
        print("final_result", final_result)
        return final_result

    def _build_input_for_agent(
        self, agent_name: str, context: dict, user_input: str
    ) -> any:
        """为不同 Agent 构建输入参数"""
        planning = context["planning"]
        if agent_name == "CopywriterAgent":
            enhanced = {
                "topic": planning.get("topic"),
                "target_audience": planning.get("target_audience"),
                "core_selling_points": planning.get("core_selling_points"),
                "tone_style": planning.get("tone_style"),
                "user_input": user_input,
                "product_context": context.get("rag_context"),  # RAG 提供的商品信息
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
                "product_category": planning.get("product_category"),
            }

        elif agent_name == "ReviewerAgent":
            copywriting = context.get("copywriting") or {}
            image = context.get("image") or {}
            return {
                "copywriting_title": copywriting.get("title", ""),
                "copywriting_content": copywriting.get("content", ""),
                "copywriting_hashtags": copywriting.get("hashtags", []),
                "image_url": image.get("image_url", ""),
                "image_prompt": image.get("prompt", ""),
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
                "hashtags": getattr(result, "hashtags", []),
            }
        elif agent_name == "ImageAgent":
            context["image"] = {
                "image_url": getattr(result, "image_url", ""),
                "prompt": getattr(result, "prompt", ""),
            }
        elif agent_name == "ReviewerAgent":
            context["review"] = {
                "approved": getattr(result, "approved", False),
                "feedback": getattr(result, "feedback", ""),
            }
        elif agent_name == "RagAgent":
            context["rag_context"] = result

    async def _execute_agent(
        self,
        agent,
        input_data,
        log_callback: Optional[Callable],
        agent_name: str,
        history: str = "",
    ):
        """执行Agent

        Args:
            agent: Agent实例
            input_data: 输入数据
            log_callback: 日志回调
            agent_name: Agent名称
            history: 历史数据

        Returns:
            执行结果
        """
        try:
            await log_callback(
                "Orchestrator",
                f"执行 {agent_name}, input: {input_data}",
            )
            if agent_name == "CopywriterAgent":
                result = await agent.run(input_data, log_callback, history=history)
            elif agent_name == "PlannerAgent":
                result = await agent.run(input_data, log_callback, history=history)
            elif agent_name == "ImageAgent":
                if isinstance(input_data, dict):
                    input_data["history"] = history
                result = await agent.run(input_data, log_callback)
            else:
                result = await agent.run(input_data, log_callback)
            await log_callback("Orchestrator", f"{agent_name} 执行成功")
            return result
        except Exception as e:
            await log_callback("Orchestrator", f"{agent_name} 执行失败: {str(e)}")
            raise

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
            "image_prompt": image.get("prompt", ""),
        }
        # 添加商品推荐
        if plan.get("product_recommendations"):
            final["product_recommendations"] = plan["product_recommendations"]
        return final
