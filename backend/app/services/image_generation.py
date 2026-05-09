from app.config import settings
from openai import AsyncOpenAI
import replicate


class ImageGenerationService:
    """图片生成服务"""

    def __init__(self):
        """初始化图片生成服务"""
        self.image_model = settings.IMAGE_MODEL
        self.client = AsyncOpenAI(
            api_key=settings.API_KEY, base_url=settings.MODEL_BASE_URL
        )
        if self.image_model == "stable-diffusion" and settings.REPLICATE_API_KEY:
            replicate.api_key = settings.REPLICATE_API_KEY

    async def generate_image(self, prompt: str, size: str = "1024x1024") -> str:
        """生成图片

        Args:
            prompt: 图片提示词
            size: 图片尺寸

        Returns:
            图片URL
        """
        try:
            # 首先尝试使用指定的模型通过OpenAI/SiliconFlow API生成图片
            response = await self.client.images.generate(
                model=self.image_model,
                prompt=prompt,
                size=size,
                quality="standard",
                n=1,
            )
            return response.data[0].url
        except Exception as e:
            # 如果OpenAI/SiliconFlow API失败，尝试使用Stable Diffusion
            print(f"使用{self.image_model}生成图片失败: {e}")
            try:
                if hasattr(replicate, "run") and settings.REPLICATE_API_KEY:
                    # 使用Stable Diffusion作为备选
                    output = await replicate.run(
                        "stability-ai/stable-diffusion:27b93a2413e7f36cd83da926f3656280b2931564ff050bf9575f1fdf9bcd7478",
                        input={
                            "prompt": prompt,
                            "width": int(size.split("x")[0]),
                            "height": int(size.split("x")[1]),
                            "num_outputs": 1,
                        },
                    )
                    return (
                        output[0]
                        if output
                        else "https://via.placeholder.com/1024x1024?text=Image+Generation+Failed"
                    )
                else:
                    # 没有备选方案，返回失败图片
                    return "https://via.placeholder.com/1024x1024?text=Image+Generation+Failed"
            except Exception as replicate_error:
                print(f"使用Stable Diffusion生成图片失败: {replicate_error}")
                # 返回默认图片URL
                return (
                    "https://via.placeholder.com/1024x1024?text=Image+Generation+Failed"
                )
