from app.agents.base_agent import BaseAgent
from app.models.schemas import ImageResult
from typing import Optional, Dict, Any
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser
from app.config import settings


class ImageAgent(BaseAgent):
    """图片生成Agent"""
    
    def __init__(self):
        """初始化图片生成Agent"""
        super().__init__("Image", "小红书图片创意专家")
        self.parser = JsonOutputParser(pydantic_object=ImageResult)
        # 构建提示模板
        template = """
        你是一位专业的小红书图片创意专家，擅长根据策划方案和文案内容生成高质量的图片提示词。
        
        策划方案：
        主题：{topic}
        目标人群：{target_audience}
        核心卖点：{core_selling_points}
        语气风格：{tone_style}
        图片需求：{image_requirements}
        产品类别：{product_category}
        
        文案内容：
        {copywriting_content}
        
        历史数据：{history}
        
        {format_instructions}
        
        要求：
        1. 生成的图片提示词要详细，包含场景、风格、元素等
        2. 图片URL暂时使用占位符，实际项目中会调用图片生成API
        3. 输出内容仅输出 JSON 对象，不要附加任何解释
        4. 请逐步思考每一步的图片创意
        """
        
        prompt = PromptTemplate(
            template=template,
            input_variables=["topic", "target_audience", "core_selling_points", "tone_style", "image_requirements", "product_category", "copywriting_content", "history"],
            partial_variables={"format_instructions": self.parser.get_format_instructions()}
        )
        
        self.llm = ChatOpenAI(
            model_name=settings.SILICONFLOW_MODEL,
            temperature=0.8,
            api_key=settings.SILICONFLOW_API_KEY,
            base_url=settings.SILICONFLOW_BASE_URL
        )
        
        self.chain = self.prompt | self.llm | self.parser
    
    async def run(self, input_data: Dict[str, Any], log_callback: Optional[callable] = None) -> ImageResult:
        """运行图片生成链
        
        Args:
            input_data: 输入数据
            log_callback: 日志回调函数
            
        Returns:
            图片结果
        """
        try:
            # 构建输入参数
            chain_input = {
                "topic": input_data.get("topic", ""),
                "target_audience": input_data.get("target_audience", []),
                "core_selling_points": input_data.get("core_selling_points", []),
                "tone_style": input_data.get("tone_style", ""),
                "image_requirements": input_data.get("image_requirements", ""),
                "product_category": input_data.get("product_category", ""),
                "copywriting_content": input_data.get("copywriting_content", ""),
                "history": input_data.get("history", "")
            }
            
            image_result = await self.chain.ainvoke(chain_input)
            await self.log(f"图片提示词生成完成", log_callback)
            
            return ImageResult(**image_result)
        except Exception as e:
            # 如果生成失败，返回默认值
            print("image chain error", e)
            return ImageResult(
                image_url="https://via.placeholder.com/800x600",
                prompt="默认图片"
            )