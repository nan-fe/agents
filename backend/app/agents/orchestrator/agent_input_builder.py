"""Agent 输入构建器"""
import json
from typing import Any, Dict
from .execution_context import ExecutionContext


class AgentInputBuilder:
    """统一的 Agent 输入构建"""

    def __init__(
        self,
        context: ExecutionContext,
        user_input: str,
        *,
        repair_mode: bool = False,
    ):
        self.context = context
        self.user_input = user_input
        self.repair_mode = repair_mode

    def _format_repair_guidance(self) -> str:
        review = self.context.review
        parts = []
        if review.feedback:
            parts.append(f"审核反馈：{review.feedback}")
        if review.corrections:
            parts.append(
                "修改建议：" + json.dumps(review.corrections, ensure_ascii=False)
            )
        return "\n".join(parts)

    def build_copywriter_input(self) -> Dict[str, Any]:
        """构建文案 Agent 输入"""
        planning = self.context.planning
        user_input = self.user_input
        if self.repair_mode:
            guidance = self._format_repair_guidance()
            if guidance:
                user_input = f"{user_input}\n\n【审核修复要求】\n{guidance}"
        return {
            "topic": planning.topic or "",
            "target_audience": planning.target_audience or [],
            "core_selling_points": planning.core_selling_points or [],
            "tone_style": planning.tone_style or "",
            "user_input": user_input,
            "product_context": self.context.rag_context,
        }

    def build_image_input(self) -> Dict[str, Any]:
        """构建图片 Agent 输入"""
        planning = self.context.planning
        copywriting = self.context.copywriting
        history = ""
        if self.repair_mode:
            history = self._format_repair_guidance()
            image_corr = (self.context.review.corrections or {}).get("image")
            if isinstance(image_corr, dict) and image_corr.get("prompt"):
                history = (
                    f"{history}\n建议配图描述：{image_corr['prompt']}".strip()
                    if history
                    else f"建议配图描述：{image_corr['prompt']}"
                )
        return {
            "image_requirements": planning.image_requirements or "",
            "copywriting_content": copywriting.content or "",
            "topic": planning.topic or "",
            "target_audience": planning.target_audience or [],
            "core_selling_points": planning.core_selling_points or [],
            "tone_style": planning.tone_style or "",
            "product_category": planning.product_category or "",
            "history": history,
        }

    def build_reviewer_input(self) -> Dict[str, Any]:
        """构建审核 Agent 输入"""
        copywriting = self.context.copywriting
        image = self.context.image
        return {
            "copywriting_title": copywriting.title,
            "copywriting_content": copywriting.content,
            "copywriting_hashtags": copywriting.hashtags,
            "image_url": image.image_url,
            "image_prompt": image.prompt,
        }

    def build_rag_input(self) -> Any:
        """构建 RAG Agent 输入"""
        product_category = (self.context.planning.product_category or "").strip()
        return product_category or self.user_input

    def build_planner_input(self) -> str:
        """构建规划 Agent 输入"""
        return self.user_input

    def build(self, agent_name: str) -> Any:
        """根据 agent 名称构建对应的输入"""
        builders = {
            "CopywriterAgent": self.build_copywriter_input,
            "ImageAgent": self.build_image_input,
            "ReviewerAgent": self.build_reviewer_input,
            "RagAgent": self.build_rag_input,
            "PlannerAgent": self.build_planner_input,
        }
        
        builder = builders.get(agent_name)
        if builder is None:
            return {}
        
        return builder()
