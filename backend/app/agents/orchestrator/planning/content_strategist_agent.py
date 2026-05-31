"""内容策划 Agent：生成创作要点（topic、卖点、语气等），由 Plan 阶段按需调用。"""
from typing import Optional

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate

from app.agents.base_agent import BaseAgent
from app.config import settings
from app.models.schemas import PlanningResult
from app.security.prompt_rules import COMMON_SECURITY_PROMPT
from app.utils.llm_factory import llm_factory


class ContentStrategistAgent(BaseAgent):
    """内容策划 Agent（领域层 brief，非编排 pipeline 规划）。"""

    def __init__(self):
        super().__init__("ContentStrategist", "小红书资深运营")
        self.parser = JsonOutputParser(pydantic_object=PlanningResult)
        template = (
            """
        你是一位小红书资深运营，擅长分析用户需求并转化为创作要点。

        """
            + COMMON_SECURITY_PROMPT
            + """

        用户输入：{input_data}
        
        历史数据：{history}

        {format_instructions}
        
        要求：
        1. 目标人群要具体，如"学生党"、"职场新人"等
        2. 核心卖点要突出产品或内容的优势
        3. 语气风格要符合小红书平台特点，如"亲切自然"、"活泼可爱"等
        4. 图片需求要详细，包括场景、风格、元素等
        5. 选题内容，25个字以内
        6. 输出内容仅输出 JSON 对象，不要附加任何解释
        7. 输出的内容必须仅包含 target_audience,tone_style,core_selling_points,image_requirements,topic,product_category
        8. 请逐步思考每一步的规划
        9. 如果有历史数据，则按照历史信息，结合用户输入的意见重新调整
        """
        )

        self.prompt = PromptTemplate(
            template=template,
            input_variables=["input_data", "history"],
            partial_variables={
                "format_instructions": self.parser.get_format_instructions()
            },
        )

    async def run(
        self,
        input_data: str,
        log_callback: Optional[callable] = None,
        history: str = "",
    ) -> PlanningResult:
        """根据用户输入生成内容策划 brief。"""
        try:
            chain_input = {"input_data": input_data, "history": history or ""}

            planning_result = await llm_factory.run_chain_with_dynamic_tokens(
                prompt_template=self.prompt,
                chain_input=chain_input,
                parser=self.parser,
                model_name=settings.BASE_MODEL,
                temperature=0.3,
                history=history,
            )
            print("plan", planning_result)
            topic = (
                planning_result.get("topic", "默认主题")
                if isinstance(planning_result, dict)
                else planning_result.topic
            )
            await self.log(f"内容策划完成，主题：{topic}", log_callback)

            return PlanningResult(**planning_result)
        except Exception as e:
            print("content strategist chain error", e)
            return PlanningResult(
                **{
                    "target_audience": ["通用人群"],
                    "core_selling_points": ["质量好", "价格实惠", "使用方便"],
                    "tone_style": "亲切自然",
                    "image_requirements": "产品实物图，清晰明亮",
                    "topic": "默认主题",
                    "product_category": "默认类别",
                }
            )
