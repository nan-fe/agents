import time
from typing import Optional, Tuple

import replicate
from openai import AsyncOpenAI

from app.agents.base_agent import BaseAgent
from app.config import settings
from app.models.schemas import ImageResult, ImageAgentInput
from app.utils.retry_policy import is_transient_exception, retry_with_backoff


class ImageAgent(BaseAgent):
    """图片Agent：主备模型 + 可恢复错误重试 + 总时间预算内降级（缩短 prompt / 降分辨率）。"""

    def __init__(self):
        """初始化图片Agent"""
        super().__init__("Image Designer", "小红书配图设计师")
        self.image_model = settings.IMAGE_MODEL
        self.client = AsyncOpenAI(
            api_key=settings.SILICONFLOW_API_KEY,
            base_url=settings.SILICONFLOW_BASE_URL,
        )
        if self.image_model == "stable-diffusion" and settings.REPLICATE_API_KEY:
            replicate.api_key = settings.REPLICATE_API_KEY

    @staticmethod
    def _compact_prompt_for_retry(prompt: str, max_chars: int = 1600) -> str:
        """重试轮次缩短上下文，降低 token/超时概率。"""
        if len(prompt) <= max_chars:
            return prompt
        half = max_chars // 2
        return (
            prompt[:half]
            + "\n...(已压缩描述以重试生图)\n"
            + prompt[-half:]
        )

    @staticmethod
    def _parse_size(size: str) -> Tuple[int, int]:
        try:
            w, h = size.lower().split("x")
            return int(w), int(h)
        except Exception:
            return 1024, 1024

    async def _siliconflow_generate(self, prompt: str, size: str) -> str:
        async def once():
            response = await self.client.images.generate(
                model=self.image_model,
                prompt=prompt,
                size=size,
                quality="standard",
                n=1,
            )
            return response.data[0].url

        return await retry_with_backoff(
            once,
            max_attempts=settings.IMAGE_HTTP_RETRY_MAX_ATTEMPTS,
            base_delay=settings.IMAGE_HTTP_RETRY_BASE_DELAY,
            max_delay=settings.IMAGE_HTTP_RETRY_MAX_DELAY,
            operation_name="siliconflow_images_generate",
            is_retryable=is_transient_exception,
        )

    async def _replicate_generate(self, prompt: str, width: int, height: int) -> str:
        async def once():
            if not (hasattr(replicate, "run") and settings.REPLICATE_API_KEY):
                raise RuntimeError("replicate_not_configured")
            output = await replicate.run(
                "stability-ai/stable-diffusion:27b93a2413e7f36cd83da926f3656280b2931564ff050bf9575f1fdf9bcd7478",
                input={
                    "prompt": prompt,
                    "width": width,
                    "height": height,
                    "num_outputs": 1,
                },
            )
            if not output:
                raise RuntimeError("replicate_empty_output")
            return output[0]

        return await retry_with_backoff(
            once,
            max_attempts=2,
            base_delay=settings.IMAGE_HTTP_RETRY_BASE_DELAY,
            max_delay=settings.IMAGE_HTTP_RETRY_MAX_DELAY,
            operation_name="replicate_stable_diffusion",
            is_retryable=is_transient_exception,
        )

    async def run(
        self,
        input_data: ImageAgentInput,
        log_callback: Optional[callable] = None,
        history: str = "",
    ) -> ImageResult:
        """运行图片Agent"""
        await self.log(f"根据策划方案生成图片描述: {input_data}", log_callback)
        if isinstance(input_data, dict):
            input_data_dict = input_data
        else:
            input_data_dict = input_data.model_dump()

        target_audience = input_data_dict.get("target_audience") or []
        if not isinstance(target_audience, list):
            target_audience = [str(target_audience)]

        core_selling_points = input_data_dict.get("core_selling_points") or []
        if not isinstance(core_selling_points, list):
            core_selling_points = [str(core_selling_points)]

        prompt = f"""
        你是一位资深电商摄影师和设计师，擅长根据商品类别和营销文案，构思出**极具真实感、像实拍照片**的商品图描述。

        请根据以下信息，生成一段用于图像生成模型（如Midjourney、DALL-E）的图片描述，要求图片看起来像是**真实拍摄**，而不是AI生成或渲染图。
        
        请根据以下信息生成一张商品介绍的图片描述：
        
        目标人群：{', '.join(target_audience)}
        核心卖点：{', '.join(core_selling_points)}
        语气风格：{input_data_dict.get("tone_style", "")}
        文案内容：{input_data_dict.get("copywriting_content", "")}
        文案主题：{input_data_dict.get("topic", "")}
        商品类别：{input_data_dict.get("product_category", "")}
        历史数据：{input_data_dict.get("history", "")}
        
        【真实感强制要求】（必须严格遵守）：
        1. **拒绝完美主义**：不要出现完美无瑕的光滑表面、零反差的柔光、过于对称的构图。允许轻微的自然瑕疵（如指纹、灰尘、布料褶皱、自然色差）。
        2. **日常环境**：将商品放置在真实生活场景中（如木桌、地毯、厨房台面、水泥地面、卧室床头），避免纯色无缝背景或影棚渐变背景。
        3. **自然或混合光线**：优先使用窗边自然光、室内暖光、阴天漫反射光，避免多灯无影布光。允许柔和阴影和轻微曝光不均。
        4. **真实色彩与质感**：色彩保持自然饱和度，不追求高艳。突出材质纹理（如棉麻的纤维、金属的拉丝、皮革的毛孔），不要过度锐化或平滑。
        5. **适度构图**：采用类似手机或入门相机随手拍的视角（如平视、轻微俯拍、略带偏移），允许非完美裁切、前景虚化、轻微镜头畸变或噪点。
        6. **生活化细节**：添加符合场景的辅助元素（如半杯咖啡、使用中的手机、散落的叶子、卷尺、购物小票），但不要喧宾夺主。
        7. **避免AI常见痕迹**：禁止出现"光晕"、"辉光"、"CGI渲染感"、"塑料质感"、"极度对称"、"无瑕疵倒影"等特征。
        8. **历史数据使用**：如果有历史数据，则按照历史信息，结合用户输入的意见重新调整图片描述。
        """

        await self.log("生成图片描述...", log_callback)
        await self.log(f"调用图片生成API（主模型 + 预算内降级）", log_callback)

        deadline = time.monotonic() + settings.IMAGE_GEN_TOTAL_BUDGET_SECONDS
        prompt_variants = [prompt, self._compact_prompt_for_retry(prompt)]
        size_variants = ["1024x1024", "512x512"]
        last_error: Optional[Exception] = None

        for i, ptext in enumerate(prompt_variants):
            if time.monotonic() > deadline:
                break
            size = size_variants[min(i, len(size_variants) - 1)]
            try:
                image_url = await self._siliconflow_generate(ptext, size)
                image_result = ImageResult(image_url=image_url, prompt=ptext)
                await self.log(f"图片生成完成: {image_result}", log_callback)
                return image_result
            except Exception as e:
                last_error = e
                print(f"使用{self.image_model}生成图片失败 (variant={i}, size={size}): {e}")
                await self.log(f"主模型生图失败，尝试降级: {e}", log_callback)

        if time.monotonic() <= deadline and hasattr(replicate, "run") and settings.REPLICATE_API_KEY:
            ptext = prompt_variants[-1]
            w, h = self._parse_size("512x512")
            try:
                image_url = await self._replicate_generate(ptext, w, h)
                image_result = ImageResult(image_url=image_url, prompt=ptext)
                await self.log(f"Replicate 备用生图完成: {image_result}", log_callback)
                return image_result
            except Exception as e:
                last_error = e
                print(f"使用Stable Diffusion生成图片失败: {e}")

        err = last_error or RuntimeError("image pipeline exhausted")
        await self.log(f"图片生成最终失败: {err}", log_callback)
        raise RuntimeError(f"图片生成失败: {err}") from err
