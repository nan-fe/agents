import time
from collections.abc import Callable
from typing import Tuple

import replicate
from openai import AsyncOpenAI

from app.agents.base_agent import BaseAgent
from app.config import settings
from app.models.schemas import ImageAgentInput, ImageResult
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
        return prompt[:half] + "\n...(已压缩描述以重试生图)\n" + prompt[-half:]

    @staticmethod
    def _parse_size(size: str) -> Tuple[int, int]:
        try:
            w, h = size.lower().split("x")
            return int(w), int(h)
        except Exception:
            return 1024, 1024

    @staticmethod
    def _build_image_prompt(input_data: dict) -> str:
        """组装可直接喂给 diffusion 的画面描述（非 LLM 任务说明）。"""
        target_audience = input_data.get("target_audience") or []
        if not isinstance(target_audience, list):
            target_audience = [str(target_audience)]

        core_selling_points = input_data.get("core_selling_points") or []
        if not isinstance(core_selling_points, list):
            core_selling_points = [str(core_selling_points)]

        product_category = input_data.get("product_category") or "商品"
        image_requirements = input_data.get("image_requirements") or "产品实物主图，清晰明亮"
        topic = input_data.get("topic") or ""
        tone_style = input_data.get("tone_style") or "自然清新"
        user_input = (input_data.get("user_input") or "").strip()
        history = (input_data.get("history") or "").strip()

        audience_text = "、".join(str(a) for a in target_audience) or "一般消费者"
        selling_text = "、".join(str(s) for s in core_selling_points)
        scene_hint = user_input or image_requirements

        parts = [
            "小红书电商产品摄影，真实照片质感，生活化静物摆拍。",
            (
                f"画面主体：{product_category}商品本体占画面约50%-70%，"
                "前景居中或45度摆放，包装与标签清晰可见，材质颜色细节可辨。"
            ),
            (
                f"场景与道具：{scene_hint}；"
                f"符合{audience_text}的日常环境，商品摆放在相关道具旁，"
                f"氛围贴合「{topic}」主题。"
            ),
            f"画面氛围：{tone_style}，温暖清新，自然舒适。",
            "拍摄效果：手机或相机实拍，自然光，真实阴影，浅景深，轻微背景虚化。",
            "真实细节：桌面纹理、布料褶皱、自然摆放的小物件。",
        ]
        if selling_text:
            parts.append(f"视觉卖点暗示：{selling_text}。")
        if history:
            parts.append(f"补充调整：{history}")
        parts.append(
            "画面中不出现：人物脸部特写、涂抹动作、AI蜡像感、3D渲染感、"
            "塑料质感、过度磨皮、不真实光效、夸张广告摆拍、完美对称摆放。"
        )
        return "\n".join(parts)

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
        log_callback: Callable | None = None,
        history: str = "",
    ) -> ImageResult:
        """运行图片Agent"""
        if isinstance(input_data, dict):
            input_data_dict = input_data
        else:
            input_data_dict = input_data.model_dump()

        prompt = self._build_image_prompt(input_data_dict)
        await self.log("正在生成配图...", log_callback)
        deadline = time.monotonic() + settings.IMAGE_GEN_TOTAL_BUDGET_SECONDS
        prompt_variants = [prompt, self._compact_prompt_for_retry(prompt)]
        size_variants = ["1024x1024", "512x512"]
        last_error: Exception | None = None

        for i, ptext in enumerate(prompt_variants):
            if time.monotonic() > deadline:
                break
            size = size_variants[min(i, len(size_variants) - 1)]
            try:
                image_url = await self._siliconflow_generate(ptext, size)
                image_result = ImageResult(image_url=image_url, prompt=ptext)
                await self.log("配图已生成", log_callback)
                return image_result
            except Exception as e:
                last_error = e
                print(f"使用{self.image_model}生成图片失败 (variant={i}, size={size}): {e}")
                await self.log("主模型生图失败，正在尝试备用方案…", log_callback)

        if (
            time.monotonic() <= deadline
            and hasattr(replicate, "run")
            and settings.REPLICATE_API_KEY
        ):
            ptext = prompt_variants[-1]
            w, h = self._parse_size("512x512")
            try:
                image_url = await self._replicate_generate(ptext, w, h)
                image_result = ImageResult(image_url=image_url, prompt=ptext)
                await self.log("备用方案配图已生成", log_callback)
                return image_result
            except Exception as e:
                last_error = e
                print(f"使用Stable Diffusion生成图片失败: {e}")

        err = last_error or RuntimeError("image pipeline exhausted")
        await self.log("配图生成失败", log_callback)
        raise RuntimeError(f"图片生成失败: {err}") from err
