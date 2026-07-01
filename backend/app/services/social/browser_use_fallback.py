"""browser-use Agent 驱动微博发布（复用项目 OpenAI 兼容 LLM，非 OpenAI 官方）。"""

from __future__ import annotations

import logging
import os
from typing import Any, Awaitable, Callable

from app.config import settings
from app.services.social.profile_paths import resolve_weibo_profile_dir

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str], Awaitable[None] | None]


def _resolve_browser_use_model() -> str:
    return (settings.BROWSER_USE_LLM_MODEL or "").strip() or settings.BASE_MODEL


def create_browser_use_llm() -> Any:
    """与创作台一致：API_KEY + MODEL_BASE_URL + 兼容模型名（如 deepseek-v4-flash）。"""
    from browser_use.llm.openai.chat import ChatOpenAI

    return ChatOpenAI(
        model=_resolve_browser_use_model(),
        api_key=settings.API_KEY,
        base_url=settings.MODEL_BASE_URL,
        temperature=0.2,
    )


def _create_cloud_llm_if_configured() -> Any | None:
    """仅当显式配置 BROWSER_USE_API_KEY 时使用 Browser Use Cloud。"""
    api_key = (os.getenv("BROWSER_USE_API_KEY") or "").strip()
    if not api_key:
        return None
    try:
        from browser_use import ChatBrowserUse
    except ImportError:
        return None
    model = _resolve_browser_use_model()
    return ChatBrowserUse(model=model)


def _build_weibo_task(*, text: str, image_path: str | None) -> str:
    parts = [
        "打开微博 https://weibo.com 。如果页面要求登录或安全验证，请先完成登录/验证。",
        "进入发微博/撰写页面。",
        "将以下正文完整复制到编辑器中：",
        text[:2000],
    ]
    if image_path:
        parts.append(f"本地配图路径：{image_path}")
    parts.extend(
        [
            "若有图片上传入口且提供了本地图片路径，请上传该图片。",
            "确认内容无误后点击发布按钮。",
            "发布成功后返回该条微博的完整链接 URL。",
        ]
    )
    return "\n".join(parts)


async def publish_via_browser_use(
    *,
    text: str,
    image_path: str | None,
    on_progress: ProgressCallback | None = None,
    required: bool = False,
) -> str | None:
    """
    使用 browser-use Agent 完成发微博。

    LLM 默认走项目已有 API_KEY + MODEL_BASE_URL（商汤等 OpenAI 兼容接口），
    不依赖 OpenAI 官方或 BROWSER_USE_API_KEY。
    """
    engine = (settings.WEIBO_PUBLISH_ENGINE or "browser_use").strip().lower()
    if not required and engine != "browser_use" and not settings.BROWSER_USE_FALLBACK_ENABLED:
        return None

    profile_dir = resolve_weibo_profile_dir()
    llm = _create_cloud_llm_if_configured() or create_browser_use_llm()
    task = _build_weibo_task(text=text, image_path=image_path)
    model_name = _resolve_browser_use_model()

    if on_progress:
        await _maybe_await(
            on_progress(f"browser-use Agent 启动（模型 {model_name}）…"),
        )

    try:
        from browser_use import Agent, BrowserProfile
    except ImportError as exc:
        msg = (
            "browser-use 未安装。请执行："
            'python3 -m pip install "browser-use>=0.12.0" -i https://pypi.org/simple'
        )
        if required:
            raise RuntimeError(msg) from exc
        logger.info(msg)
        return None

    try:
        browser_profile = BrowserProfile(
            headless=settings.WEIBO_PUBLISH_HEADLESS,
            user_data_dir=profile_dir,
            allowed_domains=["*.weibo.com", "weibo.com"],
            enable_default_extensions=False,
        )
        agent = Agent(
            task=task,
            llm=llm,
            browser_profile=browser_profile,
        )
        history = await agent.run()
    except Exception as exc:
        msg = f"browser-use Agent 执行失败: {exc}"
        if required:
            raise RuntimeError(msg) from exc
        logger.warning(msg)
        return None

    result = ""
    try:
        result = str(history.final_result() or "")
    except Exception:
        result = str(history)

    if on_progress:
        await _maybe_await(on_progress(f"browser-use 完成：{result[:200]}"))

    if "weibo.com" in result:
        return result.strip()

    if required:
        raise RuntimeError(f"browser-use 未完成发布：{result[:300]}")
    return None


async def _maybe_await(value: Awaitable[None] | None) -> None:
    if value is not None:
        await value
