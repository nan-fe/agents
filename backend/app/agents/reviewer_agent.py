from app.agents.base_agent import BaseAgent
from app.models.schemas import ReviewResult
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from app.config import settings
from app.utils.llm_factory import llm_factory
from typing import Optional


class ReviewerAgent(BaseAgent):
    """质检Agent"""

    def __init__(self):
        """初始化质检Agent"""
        super().__init__("Reviewer", "小红书内容审核")
        # 创建 Pydantic 输出解析器
        self.parser = JsonOutputParser(pydantic_object=ReviewResult)
        # 构建提示模板
        self.template = """
        你是一位小红书内容审核员，负责检查内容是否违规、合适。
        
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
        4. 内容是否符合小红书风格
        5. 图片是否清晰、美观
        6. 输出内容仅输出 JSON 对象，不要附加任何解释
        """

        self.prompt = PromptTemplate(
            template=self.template,
            input_variables=[
                "copywriting_title",
                "copywriting_content",
                "copywriting_hashtags",
                "image_url",
                "image_prompt",
            ],
            partial_variables={
                "format_instructions": self.parser.get_format_instructions()
            },
        )

    async def run(
        self, input_data: dict, log_callback: Optional[callable] = None
    ) -> ReviewResult:
        """运行质检Agent

        Args:
            input_data: 包含文案和图片信息的字典
            log_callback: 日志回调函数

        Returns:
            审核结果
        """
        # 构建输入数据
        chain_input = {
            "copywriting_title": input_data.get("copywriting_title"),
            "copywriting_content": input_data.get("copywriting_content"),
            "copywriting_hashtags": input_data.get("copywriting_hashtags"),
            "image_url": input_data.get("image_url"),
            "image_prompt": input_data.get("image_prompt"),
        }

        # 调用审核生成链
        try:
            result = await llm_factory.run_chain_with_dynamic_tokens(
                prompt_template=self.prompt,
                chain_input=chain_input,
                parser=self.parser,
                model_name=settings.BASE_MODEL,
                temperature=0.7,
            )
            await self.log(f"审核完成: {result}", log_callback)
            return ReviewResult(**result)
        except Exception as e:
            print(f"审核失败", e)
            await self.log(f"审核失败: {e}", log_callback)
            # 返回默认值
            return ReviewResult(approved=False, feedback="审核失败", corrections={})
