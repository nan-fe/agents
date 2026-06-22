from collections.abc import Callable
from typing import Any, Dict

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate

from app.agents.base_agent import BaseAgent
from app.config import settings
from app.models.schemas import ReviewCorrections, ReviewResult
from app.security.prompt_rules import REVIEWER_SECURITY_PROMPT
from app.utils.llm_factory import llm_factory


class ReviewerAgent(BaseAgent):
    """质检Agent"""

    def __init__(self):
        """初始化质检Agent"""
        super().__init__("Reviewer", "小红书内容审核")
        self.parser = JsonOutputParser(pydantic_object=ReviewResult)
        self.template = (
            """
        你是一位小红书内容审核员，负责检查内容是否违规、合适。

        """
            + REVIEWER_SECURITY_PROMPT
            + """

        请审核以下内容：
        
        文案标题：{copywriting_title}
        文案内容：{copywriting_content}
        文案标签：{copywriting_hashtags}
        图片URL: {image_url}
        图片提示词：{image_prompt}

        {format_instructions}
        
        审核标准：
        1. 内容是否违反法律法规
        2. 内容是否违反平台规则
        3. 内容是否适合目标人群
        4. 内容是否符合商品宣传的小红书风格
        5. 图片是否清晰、美观

        输出要求：
        1. approved 为 true 时 failure_category 可省略
        2. approved 为 false 时必须填写 failure_category，取值之一：
           - copywriting：文案/标题/标签/风格问题，可自动修复
           - image：配图或图片描述问题，可自动修复
           - both：文案与配图均有问题
           - policy_block：违规或不可自动修复，应停止发布
        3. corrections 结构：
           - copywriting: 可选，含 title/content/hashtags 修改建议
           - image: 可选，含 prompt 修改建议
        4. 仅输出 JSON 对象，不要附加任何解释
        """
        )

        self.prompt = PromptTemplate(
            template=self.template,
            input_variables=[
                "copywriting_title",
                "copywriting_content",
                "copywriting_hashtags",
                "image_url",
                "image_prompt",
            ],
            partial_variables={"format_instructions": self.parser.get_format_instructions()},
        )

    @staticmethod
    def _normalize_result(raw: Any) -> ReviewResult:
        if isinstance(raw, ReviewResult):
            return raw
        data: Dict[str, Any] = dict(raw) if isinstance(raw, dict) else {}
        corrections = data.get("corrections")
        if corrections is not None and not isinstance(corrections, ReviewCorrections):
            if isinstance(corrections, dict):
                data["corrections"] = ReviewCorrections(**corrections)
        return ReviewResult(**data)

    async def run(self, input_data: dict, log_callback: Callable | None = None) -> ReviewResult:
        """运行质检Agent"""
        chain_input = {
            "copywriting_title": input_data.get("copywriting_title"),
            "copywriting_content": input_data.get("copywriting_content"),
            "copywriting_hashtags": input_data.get("copywriting_hashtags"),
            "image_url": input_data.get("image_url"),
            "image_prompt": input_data.get("image_prompt"),
        }

        try:
            result = await llm_factory.run_chain_with_dynamic_tokens(
                prompt_template=self.prompt,
                chain_input=chain_input,
                parser=self.parser,
                model_name=settings.BASE_MODEL,
                temperature=0.1,
                agent_name="ReviewerAgent",
                prompt_version="reviewer_v1",
            )
            review = self._normalize_result(result)
            status = "通过" if review.approved else "需调整"
            await self.log(f"审核完成：{status}", log_callback)
            return review
        except Exception as e:
            print("审核失败", e)
            await self.log(f"审核失败: {e}", log_callback)
            return ReviewResult(
                approved=False,
                feedback="审核服务异常，请稍后重试",
                corrections=None,
                failure_category="review_error",
            )
