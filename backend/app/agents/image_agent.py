from app.agents.base_agent import BaseAgent
from app.models.schemas import ImageResult, PlanningResult
from app.services.image_generation import ImageGenerationService
from typing import Optional


class ImageAgent(BaseAgent):
    """图片Agent"""
    
    def __init__(self):
        """初始化图片Agent"""
        super().__init__("Image Designer", "小红书配图设计师")
        self.image_service = ImageGenerationService()
    
    async def run(self, input_data: PlanningResult, log_callback: Optional[callable] = None) -> ImageResult:
        """运行图片Agent
        
        Args:
            input_data: 策划结果
            log_callback: 日志回调函数
            
        Returns:
            图片结果
        """
        await self.log(f"根据策划方案生成图片描述: {input_data}", log_callback)
        
        # 生成图片描述
        prompt = f"""
        你是一位小红书配图设计师，擅长根据文案主题生成高质量的图片描述。
        
        请根据以下信息生成一张小红书风格的图片描述：
        
        目标人群：{', '.join(input_data.target_audience)}
        核心卖点：{', '.join(input_data.core_selling_points)}
        语气风格：{input_data.tone_style}
        图片需求：{input_data.image_requirements}
        
        要求：
        1. 描述要详细，包括场景、人物、物品、光线、构图等
        2. 风格要符合小红书平台特点，美观、时尚、有吸引力
        3. 语言要清晰，适合作为AI图片生成的提示词
        """
        
        await self.log("生成图片描述...", log_callback)
        
        # 这里简化处理，直接使用策划结果中的图片需求作为提示词
        # 实际项目中可以调用OpenAI生成更详细的描述
        image_prompt = input_data.image_requirements
        
        await self.log(f"调用图片生成API，提示词: {image_prompt}", log_callback)
        
        # 调用图片生成服务
        image_url = await self.image_service.generate_image(image_prompt)
        
        image_result = ImageResult(
            image_url=image_url,
            prompt=image_prompt
        )
        
        await self.log(f"图片生成完成: {image_result}", log_callback)
        return image_result
