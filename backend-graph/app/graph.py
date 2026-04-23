from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from app.models.schemas import GraphState, PlanningResult, CopywritingResult, ImageResult, ReviewResult, RoutingDecision
from app.agents.planner_agent import PlannerAgent
from app.agents.copywriter_agent import CopywriterAgent
from app.agents.image_agent import ImageAgent
from app.agents.reviewer_agent import ReviewerAgent
from app.agents.product_rag_agent import ProductRagAgent
from app.services.orchestrator_llm_service import OrchestratorLLMService
from typing import Optional, Callable, Dict, Any, List
import chromadb
import json
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import BaseMessage


class WritingSessionHistory(BaseChatMessageHistory):
    """会话历史管理类"""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.messages: List[BaseMessage] = []
        self.outputs: List[Dict[str, Any]] = []
        self.current_version = -1
        self.last_plan: Optional[Dict[str, Any]] = None
        self.last_final_result: Optional[Dict[str, Any]] = None
        self._chroma_client = chromadb.Client()
        self._collection = self._chroma_client.get_or_create_collection(name="writing_sessions")
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
        self.last_final_result = final_result
        self._save_to_db()
    
    def get_last_final_result(self) -> Optional[Dict[str, Any]]:
        return self.last_final_result
    
    def _save_to_db(self) -> None:
        session_data = {
            "messages": [msg.dict() for msg in self.messages],
            "outputs": self.outputs,
            "current_version": self.current_version,
            "last_plan": self.last_plan,
            "last_final_result": self.last_final_result
        }
        self._collection.upsert(
            documents=[json.dumps(session_data)],
            ids=[self.session_id]
        )
    
    def _load_from_db(self) -> None:
        results = self._collection.get(ids=[self.session_id])
        if results and results.get("documents"):
            session_data = json.loads(results["documents"][0])
            self.messages = [BaseMessage(**msg) for msg in session_data.get("messages", [])]
            self.outputs = session_data.get("outputs", [])
            self.current_version = session_data.get("current_version", -1)
            self.last_plan = session_data.get("last_plan", None)
            self.last_final_result = session_data.get("last_final_result", None)


class XHSAgentGraph:
    """小红书多Agent协作图"""
    
    def __init__(self, session_id: Optional[str] = None):
        """初始化Agent图

        Args:
            session_id: 会话ID，用于对话模式
        """
        self.planner_agent = PlannerAgent()
        self.copywriter_agent = CopywriterAgent()
        self.image_agent = ImageAgent()
        self.reviewer_agent = ReviewerAgent()
        self.rag_agent = ProductRagAgent()
        self.llm_service = OrchestratorLLMService()

        # 对话模式：会话历史管理
        self.session_id = session_id
        self.session_history: Optional[WritingSessionHistory] = None
        if session_id:
            self.session_history = WritingSessionHistory(session_id)

        # Agent映射表
        self.agent_map = {
            "PlannerAgent": self.planner_agent,
            "CopywriterAgent": self.copywriter_agent,
            "ImageAgent": self.image_agent,
            "ReviewerAgent": self.reviewer_agent,
            "RagAgent": self.rag_agent
        }
        
        # 使用 MemorySaver 实现状态持久化
        checkpointer = MemorySaver()
        
        # 构建图
        self.graph = StateGraph(GraphState)
        
        # 添加节点
        self.graph.add_node("intent_analyzer", self._intent_analyzer_node)
        self.graph.add_node("planner", self._planner_node)
        self.graph.add_node("rag", self._rag_node)
        self.graph.add_node("copywriter", self._copywriter_node)
        self.graph.add_node("image", self._image_node)
        self.graph.add_node("reviewer", self._reviewer_node)
        self.graph.add_node("router", self._router_node)
        self.graph.add_node("finalize", self._finalize_node)
        
        # 设置入口点和边
        self.graph.set_entry_point("intent_analyzer")
        
        # 条件边：根据意图决定下一步
        self.graph.add_conditional_edges(
            "intent_analyzer",
            self._should_regenerate_plan,
            {
                "regenerate": "planner",
                "use_history": "router"
            }
        )
        
        # 路由决策边
        self.graph.add_edge("planner", "router")
        
        # 路由决策后的条件边
        self.graph.add_conditional_edges(
            "router",
            self._route_to_next_agent,
            {
                "RagAgent": "rag",
                "CopywriterAgent": "copywriter",
                "ImageAgent": "image",
                "ReviewerAgent": "reviewer",
                "finalize": "finalize"
            }
        )
        
        # Agent执行完成后的边
        self.graph.add_edge("rag", "router")
        self.graph.add_edge("copywriter", "router")
        self.graph.add_edge("image", "router")
        self.graph.add_edge("reviewer", "router")
        
        # 最终结果
        self.graph.add_edge("finalize", END)
        
        # 编译图
        self.app = self.graph.compile(checkpointer=checkpointer)
    
    def _should_regenerate_plan(self, state: GraphState) -> str:
        """根据意图决定是否重新生成计划

        Args:
            state: 图状态

        Returns:
            决策结果：regenerate 或 use_history
        """
        intent = state.agent_outputs.get("intent", "new_task")
        
        # 如果是新任务或者没有历史计划，则重新生成
        if intent == "new_task" or not self.session_history or not self.session_history.last_plan:
            return "regenerate"
        else:
            return "use_history"
    
    def _route_to_next_agent(self, state: GraphState) -> str:
        """根据路由决策决定下一个Agent

        Args:
            state: 图状态

        Returns:
            下一个Agent的名称
        """
        routing_decision = state.routing_decision
        
        if not routing_decision or not routing_decision.agents_to_call:
            return "finalize"
        
        # 获取当前要执行的Agent
        current_agent = state.current_agent
        
        if not current_agent:
            # 首次路由，返回第一个Agent
            return routing_decision.agents_to_call[0]
        
        # 从路由决策中获取下一个Agent
        agents_to_call = routing_decision.agents_to_call
        priority_order = routing_decision.priority_order
        
        # 找到当前Agent在优先级列表中的位置
        if current_agent in priority_order:
            current_idx = priority_order.index(current_agent)
            # 返回下一个优先级的Agent
            if current_idx + 1 < len(priority_order):
                next_agent = priority_order[current_idx + 1]
                return next_agent
        
        # 如果没有更多Agent，返回finalize
        return "finalize"
    
    async def _intent_analyzer_node(self, state: GraphState) -> Dict[str, Any]:
        """意图分析节点

        Args:
            state: 图状态

        Returns:
            更新后的状态
        """
        print("=== 执行意图分析节点 ===")
        
        if not self.session_history:
            # 非对话模式，默认新任务
            return {
                "agent_outputs": {
                    **state.agent_outputs,
                    "intent": "new_task"
                }
            }
        
        # 分析用户意图
        history_messages = self.session_history.messages if self.session_history else []
        intent = await self.llm_service.analyze_intent(
            state.user_input,
            history_messages
        )
        print(f"意图分析结果: {intent}")
        
        # 如果是新任务，清除历史
        if intent == "new_task":
            if self.session_history:
                self.session_history.clear()
        
        return {
            "agent_outputs": {
                **state.agent_outputs,
                "intent": intent
            }
        }
    
    async def _planner_node(self, state: GraphState) -> Dict[str, Any]:
        """策划节点

        Args:
            state: 图状态

        Returns:
            更新后的状态
        """
        print("=== 执行策划节点 ===")
        
        # 构建历史数据
        history_data = ""
        if self.session_history and self.session_history.last_final_result:
            last_result = self.session_history.last_final_result
            history_data = f"上次生成的文案信息：\n标题：{last_result.get('title', '')}\n内容：{last_result.get('content', '')}\n标签：{', '.join(last_result.get('hashtags', []))}\n图片：{last_result.get('image_url', '')}\n图片提示：{last_result.get('image_prompt', '')}"
        
        # 运行策划Agent
        planning_result = await self.planner_agent.run(
            state.user_input,
            history=history_data
        )
        
        # 存储策划结果
        planning_dict = planning_result.model_dump()
        
        # 更新会话历史
        if self.session_history:
            self.session_history.set_last_plan(planning_dict)
        
        return {
            "planning": planning_dict,
            "current_agent": "PlannerAgent",
            "agent_outputs": {
                **state.agent_outputs,
                "planner": planning_dict,
                "history_data": history_data
            }
        }
    
    async def _rag_node(self, state: GraphState) -> Dict[str, Any]:
        """RAG节点

        Args:
            state: 图状态

        Returns:
            更新后的状态
        """
        print("=== 执行RAG节点 ===")
        
        history_data = state.agent_outputs.get("history_data", "")
        
        # 运行RAG Agent
        rag_result = await self.rag_agent.run(
            state.user_input
        )
        
        return {
            "rag_context": rag_result,
            "current_agent": "RagAgent",
            "agent_outputs": {
                **state.agent_outputs,
                "rag": rag_result
            }
        }
    
    async def _copywriter_node(self, state: GraphState) -> Dict[str, Any]:
        """文案生成节点

        Args:
            state: 图状态

        Returns:
            更新后的状态
        """
        print("=== 执行文案生成节点 ===")
        
        # 如果没有RAG上下文，先获取
        rag_context = state.rag_context
        if rag_context is None:
            rag_result = await self.rag_agent.run(state.user_input)
            rag_context = rag_result
        
        history_data = state.agent_outputs.get("history_data", "")
        
        # 构建文案生成输入
        copywriter_input = {
            "topic": state.planning.get("topic"),
            "target_audience": state.planning.get("target_audience"),
            "core_selling_points": state.planning.get("core_selling_points"),
            "tone_style": state.planning.get("tone_style"),
            "user_input": state.user_input,
            "product_context": rag_context
        }
        
        # 运行文案生成Agent
        copywriting_result = await self.copywriter_agent.run(
            copywriter_input,
            history=history_data
        )
        
        # 存储文案结果
        copywriting_dict = {
            "title": copywriting_result.title,
            "content": copywriting_result.content,
            "hashtags": copywriting_result.hashtags
        }
        
        return {
            "copywriting": copywriting_dict,
            "rag_context": rag_context,
            "current_agent": "CopywriterAgent",
            "agent_outputs": {
                **state.agent_outputs,
                "copywriter": copywriting_dict
            }
        }
    
    async def _image_node(self, state: GraphState) -> Dict[str, Any]:
        """图片生成节点

        Args:
            state: 图状态

        Returns:
            更新后的状态
        """
        print("=== 执行图片生成节点 ===")
        
        history_data = state.agent_outputs.get("history_data", "")
        
        # 构建图片生成输入
        image_input = {
            "image_requirements": state.planning.get("image_requirements"),
            "copywriting_content": state.copywriting.get("content", ""),
            "topic": state.planning.get("topic"),
            "target_audience": state.planning.get("target_audience"),
            "core_selling_points": state.planning.get("core_selling_points"),
            "tone_style": state.planning.get("tone_style"),
            "product_category": state.planning.get("product_category"),
            "history": history_data
        }
        
        # 运行图片生成Agent
        image_result = await self.image_agent.run(image_input)
        
        # 存储图片结果
        image_dict = {
            "image_url": image_result.image_url,
            "prompt": image_result.prompt
        }
        
        return {
            "image": image_dict,
            "current_agent": "ImageAgent",
            "agent_outputs": {
                **state.agent_outputs,
                "image": image_dict
            }
        }
    
    async def _reviewer_node(self, state: GraphState) -> Dict[str, Any]:
        """审核节点

        Args:
            state: 图状态

        Returns:
            更新后的状态
        """
        print("=== 执行审核节点 ===")
        
        # 构建审核输入
        reviewer_input = {
            "copywriting_title": state.copywriting.get("title", ""),
            "copywriting_content": state.copywriting.get("content", ""),
            "copywriting_hashtags": state.copywriting.get("hashtags", []),
            "image_url": state.image.get("image_url", ""),
            "image_prompt": state.image.get("prompt", "")
        }
        
        # 运行审核Agent
        review_result = await self.reviewer_agent.run(reviewer_input)
        
        # 存储审核结果
        review_dict = {
            "approved": review_result.approved,
            "feedback": review_result.feedback
        }
        
        # 如果审核不通过，重新生成文案
        if not review_result.approved:
            print("审核未通过，重新生成文案")
            
            # 使用LLM决定修正策略
            retry_decision = await self.llm_service.decide_retry_strategy(
                error_info=review_result.feedback,
                current_agent="ReviewerAgent",
                attempt_count=1,
                max_attempts=3
            )
            
            if retry_decision.action_type == "modify_params" and retry_decision.modified_params:
                # 重新生成文案
                modified_input = {
                    "topic": state.planning.get("topic"),
                    "target_audience": state.planning.get("target_audience"),
                    "core_selling_points": state.planning.get("core_selling_points"),
                    "tone_style": state.planning.get("tone_style"),
                    "user_input": state.user_input,
                    "product_context": state.rag_context,
                    "feedback": retry_decision.modified_params
                }
            else:
                # 构建修改后的文案输入
                modified_input = {
                    "topic": state.planning.get("topic"),
                    "target_audience": state.planning.get("target_audience"),
                    "core_selling_points": state.planning.get("core_selling_points"),
                    "tone_style": state.planning.get("tone_style"),
                    "user_input": state.user_input,
                    "product_context": state.rag_context,
                    "feedback": review_result.feedback
                }
            
            history_data = state.agent_outputs.get("history_data", "")
            
            # 重新生成文案
            new_copywriting_result = await self.copywriter_agent.run(
                modified_input,
                history=history_data
            )
            
            # 更新文案结果
            copywriting_dict = {
                "title": new_copywriting_result.title,
                "content": new_copywriting_result.content,
                "hashtags": new_copywriting_result.hashtags
            }
            
            return {
                "review": review_dict,
                "copywriting": copywriting_dict,
                "current_agent": "ReviewerAgent",
                "agent_outputs": {
                    **state.agent_outputs,
                    "review": review_dict,
                    "copywriter": copywriting_dict
                }
            }
        
        return {
            "review": review_dict,
            "current_agent": "ReviewerAgent",
            "agent_outputs": {
                **state.agent_outputs,
                "review": review_dict
            }
        }
    
    async def _router_node(self, state: GraphState) -> Dict[str, Any]:
        """路由决策节点

        Args:
            state: 图状态

        Returns:
            更新后的状态
        """
        print("=== 执行路由决策节点 ===")
        
        # 如果是使用历史计划，加载历史计划到状态
        if not state.planning and self.session_history and self.session_history.last_plan:
            planning = self.session_history.last_plan
            
            # 加载上次的文案和图片到上下文
            last_final = self.session_history.get_last_final_result()
            if last_final:
                copywriting = {
                    "title": last_final.get("title", ""),
                    "content": last_final.get("content", ""),
                    "hashtags": last_final.get("hashtags", [])
                }
                image = {
                    "image_url": last_final.get("image_url", ""),
                    "prompt": last_final.get("image_prompt", "")
                }
                
                return {
                    "planning": planning,
                    "copywriting": copywriting,
                    "image": image,
                    "current_agent": None,
                    "routing_decision": RoutingDecision(
                        agents_to_call=["CopywriterAgent", "ImageAgent", "ReviewerAgent"],
                        priority_order=["CopywriterAgent", "ImageAgent", "ReviewerAgent"],
                        reasoning="使用历史计划，只重新生成文案和图片"
                    ),
                    "agent_outputs": {
                        **state.agent_outputs,
                        "planning": planning,
                        "copywriting": copywriting,
                        "image": image
                    }
                }
            
            return {
                "planning": planning,
                "current_agent": None,
                "routing_decision": RoutingDecision(
                    agents_to_call=["CopywriterAgent", "ImageAgent", "ReviewerAgent"],
                    priority_order=["CopywriterAgent", "ImageAgent", "ReviewerAgent"],
                    reasoning="使用历史计划"
                ),
                "agent_outputs": {
                    **state.agent_outputs,
                    "planning": planning
                }
            }
        
        # LLM 动态路由决策
        routing_decision = await self.llm_service.route_task(
            state.user_input,
            state.planning
        )
        
        print(f"路由决策: {routing_decision.agents_to_call}, 顺序: {routing_decision.priority_order}")
        
        return {
            "routing_decision": routing_decision,
            "current_agent": None,
            "agent_outputs": {
                **state.agent_outputs,
                "routing_decision": routing_decision.model_dump()
            }
        }
    
    async def _finalize_node(self, state: GraphState) -> Dict[str, Any]:
        """最终结果节点

        Args:
            state: 图状态

        Returns:
            更新后的状态
        """
        print("=== 执行最终结果节点 ===")
        
        # 构建最终结果
        final_result = {
            "title": state.copywriting.get("title", "默认标题"),
            "content": state.copywriting.get("content", "默认内容"),
            "hashtags": state.copywriting.get("hashtags", ["#小红书", "#推荐"]),
            "image_url": state.image.get("image_url", "https://via.placeholder.com/800x600"),
            "image_prompt": state.image.get("prompt", "")
        }
        
        # 添加商品推荐
        if state.planning.get("product_recommendations"):
            final_result["product_recommendations"] = state.planning["product_recommendations"]
        
        # 保存到会话历史
        if self.session_history:
            self.session_history.add_output(final_result)
            self.session_history.set_last_final_result(final_result)
        
        return {
            "final_result": final_result,
            "current_agent": "Finalize",
            "agent_outputs": {
                **state.agent_outputs,
                "final": final_result
            }
        }
    
    async def run(self, user_input: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        """运行图

        Args:
            user_input: 用户输入
            session_id: 会话ID

        Returns:
            最终结果
        """
        # 初始化会话历史
        if session_id and not self.session_history:
            self.session_id = session_id
            self.session_history = WritingSessionHistory(session_id)
        
        # 初始化状态
        initial_state = GraphState(
            user_input=user_input,
            session_id=session_id or self.session_id
        )
        
        # 配置检查点
        config = {"configurable": {"thread_id": session_id or "default"}}
        
        # 运行图
        result = await self.app.ainvoke(initial_state, config)
        
        return result.final_result