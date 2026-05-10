"""结果映射器 - 将 Agent 执行结果映射到执行上下文"""
from typing import Any, Optional
from .execution_context import ExecutionContext


class ResultMapper:
    """结果映射器"""

    def __init__(self, context: ExecutionContext):
        """初始化映射器

        Args:
            context: 执行上下文实例
        """
        self.context = context
        self._mapping = {
            "PlannerAgent": self._map_planner_result,
            "CopywriterAgent": self._map_copywriter_result,
            "ImageAgent": self._map_image_result,
            "ReviewerAgent": self._map_reviewer_result,
            "RagAgent": self._map_rag_result,
        }

    def map_result(self, agent_name: str, result: Any) -> None:
        """根据 Agent 名称映射执行结果到上下文

        Args:
            agent_name: Agent 名称
            result: Agent 执行结果
        """
        mapper_func = self._mapping.get(agent_name)
        if mapper_func:
            mapper_func(result)

    def _map_planner_result(self, result) -> None:
        """映射 PlannerAgent 结果"""
        self.context.set_planning(result)

    def _map_copywriter_result(self, result) -> None:
        """映射 CopywriterAgent 结果"""
        self.context.set_copywriting_from_result(result)

    def _map_image_result(self, result) -> None:
        """映射 ImageAgent 结果"""
        self.context.set_image_from_result(result)

    def _map_reviewer_result(self, result) -> None:
        """映射 ReviewerAgent 结果"""
        self.context.set_review_from_result(result)

    def _map_rag_result(self, result) -> None:
        """映射 RagAgent 结果"""
        self.context.set_rag_context(result)