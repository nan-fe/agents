from app.agents.planner_agent import PlannerAgent
from app.agents.copywriter_agent import CopywriterAgent
from app.agents.image_agent import ImageAgent
from app.agents.reviewer_agent import ReviewerAgent
from app.agents.product_rag_agent import ProductRagAgent
from app.services.orchestrator_llm_service import OrchestratorLLMService
from typing import Optional, Callable, Dict, Any
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import BaseMessage
import chromadb
import json
from dotenv import load_dotenv

load_dotenv()


class WritingSessionHistory(BaseChatMessageHistory):
    def __init__(self, session_id):
        self.session_id = session_id
        self.messages = []  # 用户-Agent对话历史
        self.outputs = []  # 每一轮生成的完整文案（版本列表）
        self.current_version = -1  # 当前展示的版本索引
        self.last_plan = None  # 最近一次生成的大纲
        self.last_final_result = None  # 最近一次完整的FinalResult结果
        self._chroma_client = chromadb.Client()
        self._collection = self._chroma_client.get_or_create_collection(
            name="writing_sessions"
        )
        self._load_from_db()

    def add_message(self, message: BaseMessage) -> None:
        self.messages.append(message)
        self._save_to_db()

    def clear(self) -> None:
        self.messages = []
        self.outputs = []
        self.current_version = -1
        self.last_plan = None
        self.last_final_result = None
        self._save_to_db()

    def add_output(self, output: Dict[str, Any]) -> None:
        self.outputs.append(output)
        self.current_version = len(self.outputs) - 1
        self._save_to_db()

    def set_last_plan(self, plan: Dict[str, Any]) -> None:
        self.last_plan = plan
        self._save_to_db()

    def set_last_final_result(self, final_result: Dict[str, Any]) -> None:
        """存储完整的FinalResult结果

        Args:
            final_result: 包含title, content, hashtags, image_url等信息的字典
        """
        self.last_final_result = final_result
        self._save_to_db()

    def get_last_final_result(self) -> Optional[Dict[str, Any]]:
        """获取最近一次完整的FinalResult结果

        Returns:
            包含title, content, hashtags, image_url等信息的字典，如果没有则返回None
        """
        return self.last_final_result

    def _save_to_db(self) -> None:
        session_data = {
            "messages": [msg.dict() for msg in self.messages],
            "outputs": self.outputs,
            "current_version": self.current_version,
            "last_plan": self.last_plan,
            "last_final_result": self.last_final_result,
        }
        self._collection.upsert(
            documents=[json.dumps(session_data)], ids=[self.session_id]
        )

    def _load_from_db(self) -> None:
        results = self._collection.get(ids=[self.session_id])
        if results and results.get("documents"):
            session_data = json.loads(results["documents"][0])
            self.messages = [
                BaseMessage(**msg) for msg in session_data.get("messages", [])
            ]
            self.outputs = session_data.get("outputs", [])
            self.current_version = session_data.get("current_version", -1)
            self.last_plan = session_data.get("last_plan", None)
            self.last_final_result = session_data.get("last_final_result", None)


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
        """获取会话历史

        Args:
            session_id: 会话ID

        Returns:
            WritingSessionHistory实例
        """
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
        await log_callback("Orchestrator", "开始智能任务编排...")

        # 分析用户意图和会话历史
        intent = await self.llm_service.analyze_intent(
            user_input, session_history.messages
        )
        await log_callback("Orchestrator", f"用户意图分析: {intent}")

        # 如果是询问问题，直接提示用户
        if intent == "ask_question":
            await log_callback("Orchestrator", "检测到询问问题，引导用户输入创作需求")
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

        # 准备历史数据
        last_final_result = session_history.get_last_final_result()
        history_data = ""
        if last_final_result:
            history_data = f"上次生成的文案信息：\n标题：{last_final_result.get('title', '')}\n内容：{last_final_result.get('content', '')}\n标签：{', '.join(last_final_result.get('hashtags', []))}\n图片：{last_final_result.get('image_url', '')}\n图片提示：{last_final_result.get('image_prompt', '')}"

            print("准备历史数据完成", history_data)
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
            session_history.set_last_plan(execution_context["planning"])
        else:
            # 使用历史计划
            await log_callback("Orchestrator", "使用历史计划")
            print("历史计划", session_history.last_plan, execution_context["planning"])

            # 如果不是新任务，读取上次的FinalResult信息到执行上下文
            if last_final_result:
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
            f"路由决策: 调用 {routing_decision.agents_to_call}, 顺序: {routing_decision.priority_order}",
        )

        # 按优先级顺序执行 Agent
        for agent_name in routing_decision.priority_order:
            if agent_name not in self.agent_map:
                await log_callback("Orchestrator", f"未知 Agent: {agent_name}，跳过")
                continue

            # 特殊处理：如果当前是 CopywriterAgent 且 RAG 上下文尚未加载，则先调用 RagAgent
            if (
                agent_name == "CopywriterAgent"
                and execution_context["rag_context"] is None
            ):
                await log_callback(
                    "Orchestrator",
                    "检测到需要生成文案，正在调用 RagAgent 获取商品上下文...",
                )
                rag_result = await self._execute_with_retry(
                    self.rag_agent,
                    user_input,
                    log_callback,
                    "RagAgent",
                    history=history_data,
                )
                execution_context["rag_context"] = rag_result
                await log_callback("Orchestrator", "RAG 商品上下文已加载")

            # 构建当前 Agent 的输入
            agent_input = self._build_input_for_agent(
                agent_name, execution_context, user_input
            )
            print("agent_input", agent_name, agent_input)
            # 执行 Agent
            agent = self.agent_map[agent_name]
            result = await self._execute_with_retry(
                agent, agent_input, log_callback, agent_name, history=history_data
            )

            # 存储结果
            self._store_result_to_context(agent_name, result, execution_context)

            # 如果审核不通过，尝试修正（重新生成文案）
            if (
                agent_name == "ReviewerAgent"
                and hasattr(result, "approved")
                and not result.approved
            ):
                await self._handle_review_failure(execution_context, log_callback)

        # 整合最终结果
        final_result = self._build_final_result(execution_context)

        # 保存结果到会话历史
        session_history.add_output(final_result)

        # 存储完整的FinalResult信息，供下次对话使用
        session_history.set_last_final_result(final_result)

        await log_callback("Orchestrator", "多Agent协作完成，生成最终结果")
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
            print("planning", planning.get("target_audience"))
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

    async def _execute_with_retry(
        self,
        agent,
        input_data,
        log_callback: Optional[Callable],
        agent_name: str,
        history: str = "",
        max_attempts: int = 3,
    ):
        """执行Agent并支持自适应重试

        Args:
            agent: Agent实例
            input_data: 输入数据
            log_callback: 日志回调
            agent_name: Agent名称
            history: 历史数据
            max_attempts: 最大尝试次数

        Returns:
            执行结果
        """
        attempt_count = 0
        last_error = None

        while attempt_count < max_attempts:
            attempt_count += 1
            try:
                await log_callback(
                    "Orchestrator",
                    f"执行 {agent_name}，第 {attempt_count} 次尝试,{input_data}",
                )
                # 根据Agent类型传递不同的参数
                if agent_name == "CopywriterAgent":
                    result = await agent.run(input_data, log_callback, history=history)
                elif agent_name == "PlannerAgent":
                    result = await agent.run(input_data, log_callback, history=history)
                elif agent_name == "ImageAgent":
                    # 为ImageAgent添加历史数据
                    if isinstance(input_data, dict):
                        input_data["history"] = history
                    result = await agent.run(input_data, log_callback)
                else:
                    print("retry", agent_name, input_data)
                    result = await agent.run(input_data, log_callback)
                await log_callback("Orchestrator", f"{agent_name} 执行成功")
                return result
            except Exception as e:
                last_error = str(e)
                await log_callback(
                    "Orchestrator", f"{agent_name} 执行失败: {last_error}"
                )
                print("last_error", agent_name, last_error)

                # 使用LLM决定重试策略
                retry_decision = await self.llm_service.decide_retry_strategy(
                    error_info=last_error,
                    current_agent=agent_name,
                    attempt_count=attempt_count,
                    max_attempts=max_attempts,
                )

                await log_callback(
                    "Orchestrator",
                    f"重试决策: {retry_decision.action_type}, 理由: {retry_decision.reasoning}",
                )

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
                        await log_callback(
                            "Orchestrator", f"切换到 {target_agent_name}"
                        )
                elif retry_decision.action_type == "modify_params":
                    # 修改参数
                    if retry_decision.modified_params:
                        input_data = self._merge_params(
                            input_data, retry_decision.modified_params
                        )
                        await log_callback(
                            "Orchestrator",
                            f"修改参数: {retry_decision.modified_params}",
                        )

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

        # 使用 LLM 决定修正策略
        retry_decision = await self.llm_service.decide_retry_strategy(
            error_info=review.get("feedback", "审核未通过"),
            current_agent="ReviewerAgent",
            attempt_count=1,
            max_attempts=3,
        )

        if (
            retry_decision.action_type == "modify_params"
            and retry_decision.modified_params
        ):
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
                title="默认标题", content="默认内容", hashtags=["#小红书", "#推荐"]
            )
        elif agent_name == "ImageAgent":
            return ImageResult(
                image_url="https://via.placeholder.com/800x600", prompt="默认图片"
            )
        elif agent_name == "ReviewerAgent":
            return ReviewResult(approved=True, feedback="默认通过")
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
            "image_prompt": image.get("prompt", ""),
        }
        # 添加商品推荐
        if plan.get("product_recommendations"):
            final["product_recommendations"] = plan["product_recommendations"]
        return final
