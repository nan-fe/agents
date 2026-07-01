"""微博 Playwright 发布实现。"""

from __future__ import annotations

import logging
import tempfile
import time
from pathlib import Path
from typing import Awaitable, Callable
from urllib.parse import urlparse

import httpx

from app.config import settings
from app.services.social.browser_use_fallback import publish_via_browser_use
from app.services.social.content_adapter import (
    WeiboPublishPayload,
    is_likely_logged_in_url,
)
from app.services.social.profile_paths import resolve_weibo_profile_dir

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str], Awaitable[None] | None]

_login_state_cache: tuple[float, dict[str, object]] | None = None
_LOGIN_STATE_CACHE_TTL_SEC = 30

_COMPOSE_URLS = (
    "https://weibo.com/",
)

_TEXTAREA_SELECTORS = (
    "textarea",
    "[contenteditable='true']",
    "[node-type='textEl']",
    "div[class*='Form_input']",
    "div[class*='woo-input-textarea'] textarea",
)

_PUBLISH_BUTTON_SELECTORS = (
    "button:has-text('发布')",
    "a:has-text('发布')",
    "[node-type='submit']",
    "button:has-text('发送')",
)

_LOGIN_MARKERS = (
    "passport.weibo.com",
    "login.sina.com.cn",
    "newlogin",
    "扫码登录",
    "账号登录",
    "注册",
    "该账号行为异常",
    "存在安全风险",
    "用户验证",
)


def _screenshot_dir() -> Path:
    base = Path(__file__).resolve().parents[2] / "data" / "social_screenshots"
    base.mkdir(parents=True, exist_ok=True)
    return base


async def _emit(on_progress: ProgressCallback | None, message: str) -> None:
    if on_progress is not None:
        result = on_progress(message)
        if result is not None:
            await result


async def _download_image(url: str) -> Path | None:
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            suffix = ".jpg"
            parsed = urlparse(url)
            if parsed.path.lower().endswith((".png", ".webp", ".gif", ".jpeg", ".jpg")):
                suffix = Path(parsed.path).suffix or suffix
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            tmp.write(resp.content)
            tmp.close()
            return Path(tmp.name)
    except Exception as exc:
        logger.warning("下载配图失败: %s", exc)
        return None


async def check_weibo_login_state(*, force_refresh: bool = False) -> dict[str, object]:
    """检测微博登录态（轻量访问首页，后台 headless，带短缓存）。"""
    global _login_state_cache

    if not settings.WEIBO_PUBLISH_ENABLED:
        return {"configured": False, "logged_in": False, "reason": "未启用微博发布"}
    profile_dir = resolve_weibo_profile_dir()
    if settings.WEIBO_PUBLISH_DRY_RUN:
        return {"configured": True, "logged_in": True, "dry_run": True}

    if not force_refresh and _login_state_cache is not None:
        cached_at, cached_result = _login_state_cache
        if time.time() - cached_at < _LOGIN_STATE_CACHE_TTL_SEC:
            return cached_result

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return {"configured": False, "logged_in": False, "reason": "playwright 未安装"}

    try:
        async with async_playwright() as playwright:
            # 状态检测始终 headless，避免每次 /social/status 弹出浏览器窗口。
            context = await _launch_context(playwright, headless=True)
            pages = context.pages  # type: ignore[attr-defined]
            page = pages[0] if pages else await context.new_page()  # type: ignore[attr-defined]
            await page.goto("https://weibo.com", wait_until="domcontentloaded", timeout=settings.WEIBO_PUBLISH_TIMEOUT_MS)  # type: ignore[attr-defined]
            await page.wait_for_timeout(1500)  # type: ignore[attr-defined]
            url = page.url  # type: ignore[attr-defined]
            body = await page.content()  # type: ignore[attr-defined]
            logged_in = is_likely_logged_in_url(url) and not any(m in body for m in _LOGIN_MARKERS)
            await context.close()  # type: ignore[attr-defined]
            result = {
                "configured": True,
                "logged_in": logged_in,
                "current_url": url,
                "profile_path": profile_dir,
            }
            _login_state_cache = (time.time(), result)
            return result
    except Exception as exc:
        logger.warning("微博登录态检测失败: %s", exc)
        result = {"configured": True, "logged_in": False, "reason": str(exc)}
        _login_state_cache = (time.time(), result)
        return result


async def _launch_context(playwright: object, *, headless: bool | None = None) -> object:
    profile_dir = resolve_weibo_profile_dir()
    launch_kwargs: dict = {
        "headless": settings.WEIBO_PUBLISH_HEADLESS if headless is None else headless,
        "args": ["--disable-blink-features=AutomationControlled"],
    }
    chromium = playwright.chromium  # type: ignore[attr-defined]
    context = await chromium.launch_persistent_context(
        user_data_dir=profile_dir,
        **launch_kwargs,
        viewport={"width": 1280, "height": 900},
        locale="zh-CN",
    )
    return context


async def _fill_compose(page: object, text: str) -> bool:
    for trigger_text in ("有什么新鲜事想分享给大家", "分享新鲜事", "发微博"):
        try:
            trigger = page.get_by_text(trigger_text).first  # type: ignore[attr-defined]
            if await trigger.count() > 0:
                await trigger.click(timeout=3000)
                await page.wait_for_timeout(1000)  # type: ignore[attr-defined]
                break
        except Exception:
            continue

    for selector in _TEXTAREA_SELECTORS:
        try:
            locator = page.locator(selector).first  # type: ignore[attr-defined]
            if await locator.count() == 0:
                continue
            await locator.click(timeout=3000)
            await locator.fill(text, timeout=5000)
            return True
        except Exception:
            continue
    try:
        editable = page.locator("[contenteditable='true']").first  # type: ignore[attr-defined]
        await editable.click(timeout=3000)
        await editable.type(text, delay=10)
        return True
    except Exception:
        return False


async def _click_publish(page: object) -> bool:
    for selector in _PUBLISH_BUTTON_SELECTORS:
        try:
            btn = page.locator(selector).first  # type: ignore[attr-defined]
            if await btn.count() == 0:
                continue
            await btn.click(timeout=5000)
            return True
        except Exception:
            continue
    return False


async def _upload_image(page: object, image_path: Path) -> bool:
    selectors = (
        "input[type='file']",
        "input[accept*='image']",
    )
    for selector in selectors:
        try:
            inp = page.locator(selector).first  # type: ignore[attr-defined]
            if await inp.count() == 0:
                continue
            await inp.set_input_files(str(image_path), timeout=10000)
            await page.wait_for_timeout(2000)  # type: ignore[attr-defined]
            return True
        except Exception:
            continue
    return False


async def publish_to_weibo(
    payload: WeiboPublishPayload,
    *,
    on_progress: ProgressCallback | None = None,
) -> tuple[str | None, str | None]:
    """
    发布到微博。

    Returns:
        (post_url, screenshot_path_on_failure)
    """
    if settings.WEIBO_PUBLISH_DRY_RUN:
        await _emit(on_progress, "DRY RUN：模拟发布成功")
        return "https://weibo.com/dry-run", None

    if not settings.WEIBO_PUBLISH_ENABLED:
        raise ValueError("微博发布未启用（WEIBO_PUBLISH_ENABLED=false）")

    resolve_weibo_profile_dir()

    engine = (settings.WEIBO_PUBLISH_ENGINE or "browser_use").strip().lower()

    image_path: Path | None = None
    if payload.image_url:
        await _emit(on_progress, "下载配图中…")
        image_path = await _download_image(payload.image_url)

    try:
        if engine == "browser_use":
            await _emit(on_progress, "browser-use Agent 打开微博并发布…")
            try:
                post_url = await publish_via_browser_use(
                    text=payload.text,
                    image_path=str(image_path) if image_path else None,
                    on_progress=on_progress,
                    required=True,
                )
                if not post_url:
                    raise RuntimeError("browser-use 发布未返回微博链接")
                return post_url, None
            except Exception as exc:
                if not settings.BROWSER_USE_FALLBACK_ENABLED:
                    raise
                await _emit(
                    on_progress,
                    f"browser-use 失败，改用 Playwright：{exc}",
                )
                return await _publish_via_playwright(
                    payload,
                    image_path=image_path,
                    on_progress=on_progress,
                    allow_browser_use_fallback=False,
                )

        return await _publish_via_playwright(
            payload,
            image_path=image_path,
            on_progress=on_progress,
        )
    finally:
        if image_path is not None:
            try:
                image_path.unlink(missing_ok=True)
            except OSError:
                pass


async def _publish_via_playwright(
    payload: WeiboPublishPayload,
    *,
    image_path: Path | None,
    on_progress: ProgressCallback | None = None,
    allow_browser_use_fallback: bool = True,
) -> tuple[str | None, str | None]:
    from playwright.async_api import async_playwright

    screenshot_path: str | None = None
    try:
        async with async_playwright() as playwright:
            await _emit(on_progress, "启动 Playwright 浏览器…")
            context = await _launch_context(playwright)
            pages = context.pages  # type: ignore[attr-defined]
            page = pages[0] if pages else await context.new_page()  # type: ignore[attr-defined]

            opened = False
            for url in _COMPOSE_URLS:
                try:
                    await _emit(on_progress, f"打开 {url}")
                    await page.goto(url, wait_until="domcontentloaded", timeout=settings.WEIBO_PUBLISH_TIMEOUT_MS)  # type: ignore[attr-defined]
                    await page.wait_for_timeout(2000)  # type: ignore[attr-defined]
                    opened = True
                    break
                except Exception:
                    continue
            if not opened:
                raise RuntimeError("无法打开微博页面")

            current_url = page.url  # type: ignore[attr-defined]
            body = await page.content()  # type: ignore[attr-defined]
            if not is_likely_logged_in_url(current_url) or any(m in body for m in _LOGIN_MARKERS):
                raise RuntimeError("微博未登录或需要安全验证，请使用 BROWSER_USE_PROFILE_PATH 预先登录并完成验证")

            await _emit(on_progress, "填写正文…")
            filled = await _fill_compose(page, payload.text)
            if not filled:
                raise RuntimeError("未找到微博编辑器")

            if image_path is not None:
                await _emit(on_progress, "上传配图…")
                uploaded = await _upload_image(page, image_path)
                if not uploaded:
                    await _emit(on_progress, "配图上传失败，继续纯文本发布")

            await _emit(on_progress, "点击发布…")
            published = await _click_publish(page)
            if not published:
                raise RuntimeError("未找到发布按钮")

            await page.wait_for_timeout(3000)  # type: ignore[attr-defined]
            post_url = page.url  # type: ignore[attr-defined]
            await context.close()  # type: ignore[attr-defined]
            await _emit(on_progress, "发布完成")
            return post_url, None
    except Exception as primary_exc:
        logger.warning("Playwright 微博发布失败: %s", primary_exc)
        shot = _screenshot_dir() / f"weibo_fail_{int(time.time())}.png"
        screenshot_path = str(shot)
        try:
            async with async_playwright() as playwright:
                context = await _launch_context(playwright)
                page = context.pages[0] if context.pages else await context.new_page()  # type: ignore[attr-defined]
                await page.screenshot(path=screenshot_path, full_page=True)  # type: ignore[attr-defined]
                await context.close()  # type: ignore[attr-defined]
        except Exception:
            screenshot_path = None

        if allow_browser_use_fallback and settings.BROWSER_USE_FALLBACK_ENABLED:
            await _emit(on_progress, "Playwright 失败，尝试 browser-use 兜底…")
            fallback_url = await publish_via_browser_use(
                text=payload.text,
                image_path=str(image_path) if image_path else None,
                on_progress=on_progress,
                required=False,
            )
            if fallback_url:
                return fallback_url, None
        raise RuntimeError(str(primary_exc)) from primary_exc
