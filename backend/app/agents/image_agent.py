from app.agents.base_agent import BaseAgent
from app.models.schemas import ImageResult, ImageAgentInput
from app.services.image_generation import ImageGenerationService
from typing import Optional


class ImageAgent(BaseAgent):
    """图片Agent"""
    
    def __init__(self):
        """初始化图片Agent"""
        super().__init__("Image Designer", "小红书配图设计师")
        self.image_service = ImageGenerationService()
    
    async def run(self, input_data: ImageAgentInput, log_callback: Optional[callable] = None) -> ImageResult:
        """运行图片Agent
        
        Args:
            input_data: 策划结果
            log_callback: 日志回调函数
            
        Returns:
            图片结果
        """
        await self.log(f"根据策划方案生成图片描述: {input_data}", log_callback)
        print("image input_data",input_data.get('target_audience'))
        # 图片需求：{input_data.image_requirements}
        # 生成图片描述
        prompt = f"""
        你是一位资深电商摄影师和设计师，擅长根据商品类别和营销文案，构思出**极具真实感、像实拍照片**的商品图描述。
        请根据以下信息，生成一段用于图像生成模型（如Midjourney、DALL-E）的图片描述，要求图片看起来像是**真实拍摄**，而不是AI生成或渲染图。
        
        请根据以下信息生成一张商品介绍的图片描述：
        
        目标人群：{', '.join(input_data.get('target_audience'))}
        核心卖点：{', '.join(input_data.get("core_selling_points"))}
        语气风格：{input_data.get("tone_style")}
        文案内容：{input_data.get("copywriting_content")}
        文案主题：{input_data.get("topic")}
        商品类别：{input_data.get("product_category")}
        历史数据：{input_data.get("history", "")}
        
        【真实感强制要求】（必须严格遵守）：
        1. **拒绝完美主义**：不要出现完美无瑕的光滑表面、零反差的柔光、过于对称的构图。允许轻微的自然瑕疵（如指纹、灰尘、布料褶皱、自然色差）。
        2. **日常环境**：将商品放置在真实生活场景中（如木桌、地毯、厨房台面、水泥地面、卧室床头），避免纯色无缝背景或影棚渐变背景。
        3. **自然或混合光线**：优先使用窗边自然光、室内暖光、阴天漫反射光，避免多灯无影布光。允许柔和阴影和轻微曝光不均。
        4. **真实色彩与质感**：色彩保持自然饱和度，不追求高艳。突出材质纹理（如棉麻的纤维、金属的拉丝、皮革的毛孔），不要过度锐化或平滑。
        5. **适度构图**：采用类似手机或入门相机随手拍的视角（如平视、轻微俯拍、略带偏移），允许非完美裁切、前景虚化、轻微镜头畸变或噪点。
        6. **生活化细节**：添加符合场景的辅助元素（如半杯咖啡、使用中的手机、散落的叶子、卷尺、购物小票），但不要喧宾夺主。
        7. **避免AI常见痕迹**：禁止出现“光晕”、“辉光”、“CGI渲染感”、“塑料质感”、“极度对称”、“无瑕疵倒影”等特征。
        8. **历史数据使用**：如果有历史数据，则按照历史信息，结合用户输入的意见重新调整图片描述。
        """
        
        await self.log("生成图片描述...", log_callback)
        
        # 这里简化处理，直接使用策划结果中的图片需求作为提示词
        # 实际项目中可以调用OpenAI生成更详细的描述
        image_prompt = prompt
        await self.log(f"调用图片生成API，提示词: {image_prompt}", log_callback)
        
        # 调用图片生成服务
        # image_url = await self.image_service.generate_image(image_prompt)
        image_url='https://bizyair-prod.oss-cn-shanghai.aliyuncs.com/outputs/2697b788-7795-4f36-8f7e-c1ea20bd61b8_6e9dfbbfb65c2b4d99bdbc0d2f76ce3b_ComfyUI_21ec1493_00001_.png'
        image_result = ImageResult(
            image_url=image_url,
            prompt=image_prompt
        )
        
        await self.log(f"图片生成完成: {image_result}", log_callback)
        return image_result
