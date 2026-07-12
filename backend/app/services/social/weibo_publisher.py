"""微博 Playwright 发布实现。"""

from __future__ import annotations

import asyncio
import logging
import tempfile
import time
from pathlib import Path
from typing import Awaitable, Callable
from urllib.parse import urlparse

import httpx

from app.config import settings
from app.services.social.content_adapter import (
    WeiboPublishPayload,
    is_likely_logged_in_url,
)
from app.services.social.profile_paths import (
    clear_stale_chromium_profile_lock,
    resolve_weibo_profile_dir,
    weibo_profile_lock,
)
from app.services.social.weibo_auth_store import get_weibo_auth

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str], Awaitable[None] | None]

_login_state_cache: dict[str, tuple[float, dict[str, object]]] = {}
_LOGIN_STATE_CACHE_TTL_SEC = 300
_login_check_lock = asyncio.Lock()
_playwright_profile_lock = weibo_profile_lock

VIEWPORT_WIDTH = 1280
VIEWPORT_HEIGHT = 900

_CHROMIUM_STEALTH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-infobars",
]

_STEALTH_INIT_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
"""


def invalidate_weibo_login_state_cache(user_id: str = "") -> None:
    """登录成功后清除短缓存，使 /social/status 立即反映新状态。"""
    uid = (user_id or "").strip()
    if uid:
        _login_state_cache.pop(uid, None)
    else:
        _login_state_cache.clear()


_COMPOSE_URLS = ("https://weibo.com/",)

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


async def _check_weibo_login_state_playwright(user_id: str) -> dict[str, object]:
    from playwright.async_api import async_playwright

    profile_dir = resolve_weibo_profile_dir(user_id)
    async with weibo_profile_lock:
        async with async_playwright() as playwright:
            context = await _launch_context(playwright, user_id=user_id, headless=True)
            pages = context.pages  # type: ignore[attr-defined]
            page = pages[0] if pages else await context.new_page()  # type: ignore[attr-defined]
            await page.goto(
                "https://weibo.com",
                wait_until="domcontentloaded",
                timeout=settings.WEIBO_PUBLISH_TIMEOUT_MS,
            )  # type: ignore[attr-defined]
            await page.wait_for_timeout(1500)  # type: ignore[attr-defined]
            url = page.url  # type: ignore[attr-defined]
            body = await page.content()  # type: ignore[attr-defined]
            logged_in = is_likely_logged_in_url(url) and not any(m in body for m in _LOGIN_MARKERS)
            await context.close()  # type: ignore[attr-defined]
            return {
                "configured": True,
                "logged_in": logged_in,
                "current_url": url,
                "profile_path": profile_dir,
                "driver": "playwright",
                "user_id": user_id,
            }


async def check_weibo_login_state(
    *, user_id: str, force_refresh: bool = False
) -> dict[str, object]:
    """检测微博登录态。默认走缓存/DB；force_refresh 才启动浏览器验证。"""
    uid = (user_id or "").strip()
    if not uid:
        return {"configured": False, "logged_in": False, "reason": "user_id 不能为空"}

    if not settings.WEIBO_PUBLISH_ENABLED:
        return {"configured": False, "logged_in": False, "reason": "未启用微博发布"}
    if settings.WEIBO_PUBLISH_DRY_RUN:
        return {"configured": True, "logged_in": True, "dry_run": True, "user_id": uid}

    profile_dir = resolve_weibo_profile_dir(uid)

    stored = await get_weibo_auth(uid)
    if stored and stored.get("logged_in") and stored.get("profile_path") == profile_dir:
        return {
            "configured": True,
            "logged_in": True,
            "profile_path": profile_dir,
            "current_url": stored.get("current_url"),
            "confirmed_at": stored.get("confirmed_at"),
            "driver": "playwright",
            "user_id": uid,
        }

    cached = _login_state_cache.get(uid)
    if cached is not None:
        cached_at, cached_result = cached
        if time.time() - cached_at < _LOGIN_STATE_CACHE_TTL_SEC:
            return cached_result

    if not force_refresh:
        return {
            "configured": True,
            "logged_in": False,
            "reason": "未检测",
            "profile_path": profile_dir,
            "user_id": uid,
        }

    async with _login_check_lock:
        cached = _login_state_cache.get(uid)
        if cached is not None:
            cached_at, cached_result = cached
            if time.time() - cached_at < _LOGIN_STATE_CACHE_TTL_SEC:
                return cached_result

        try:
            result = await _check_weibo_login_state_playwright(uid)
            result["user_id"] = uid
            if result.get("logged_in"):
                from app.services.social.weibo_auth_store import save_weibo_auth

                await save_weibo_auth(
                    user_id=uid,
                    profile_path=profile_dir,
                    logged_in=True,
                    current_url=str(result.get("current_url") or ""),
                )
            _login_state_cache[uid] = (time.time(), result)
            return result
        except ImportError:
            return {"configured": False, "logged_in": False, "reason": "playwright 未安装"}
        except Exception as exc:
            logger.warning("微博登录态检测失败 user_id=%s: %s", uid, exc)
            result = {
                "configured": True,
                "logged_in": False,
                "reason": str(exc),
                "user_id": uid,
            }
            _login_state_cache[uid] = (time.time(), result)
            return result


def is_chromium_profile_lock_error(exc: BaseException) -> bool:
    message = str(exc).lower()
    return "profile appears to be in use" in message or "processsingleton" in message


def format_weibo_browser_error(exc: BaseException) -> str:
    message = str(exc)
    if is_chromium_profile_lock_error(exc):
        return (
            "微博浏览器 Profile 被占用，请稍后重试；"
            "若持续失败，请联系管理员清理 Profile 目录中的锁文件"
        )
    if "executable doesn't exist" in message.lower():
        return "服务器未安装 Playwright Chromium，请联系管理员执行 playwright install chromium"
    first_line = message.splitlines()[0].strip()
    if len(first_line) > 240:
        return first_line[:240] + "…"
    return first_line or "无法启动微博登录浏览器"


async def _launch_context(
    playwright: object,
    *,
    user_id: str = "",
    headless: bool | None = None,
    for_login: bool = False,
) -> object:
    """启动 Playwright 持久化 Profile。

    for_login=True 时使用本机 Chrome + 反自动化指纹，便于用户手动过微博验证码。
    """
    profile_dir = resolve_weibo_profile_dir(user_id)
    resolved_headless = settings.WEIBO_PUBLISH_HEADLESS if headless is None else headless
    channel = (settings.WEIBO_BROWSER_CHANNEL or "").strip()

    launch_kwargs: dict = {
        "headless": resolved_headless,
        "user_data_dir": profile_dir,
        "args": list(_CHROMIUM_STEALTH_ARGS),
        "ignore_default_args": ["--enable-automation"],
        "locale": "zh-CN",
    }
    if for_login and not resolved_headless:
        launch_kwargs["no_viewport"] = True
    else:
        launch_kwargs["viewport"] = {"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT}
    if channel:
        launch_kwargs["channel"] = channel

    chromium = playwright.chromium  # type: ignore[attr-defined]

    async def _try_launch(kwargs: dict) -> object:
        clear_stale_chromium_profile_lock(profile_dir)
        try:
            return await chromium.launch_persistent_context(**kwargs)
        except Exception as exc:
            if not is_chromium_profile_lock_error(exc):
                raise
            removed = clear_stale_chromium_profile_lock(profile_dir)
            if not removed:
                raise
            logger.warning("检测到过期 Profile 锁，清理后重试启动浏览器")
            return await chromium.launch_persistent_context(**kwargs)

    try:
        context = await _try_launch(launch_kwargs)
    except Exception as exc:
        if not channel:
            raise
        logger.warning(
            "无法用 channel=%s 启动浏览器，回退到 Playwright Chromium: %s",
            channel,
            exc,
        )
        fallback_kwargs = {k: v for k, v in launch_kwargs.items() if k != "channel"}
        context = await _try_launch(fallback_kwargs)

    await context.add_init_script(_STEALTH_INIT_SCRIPT)  # type: ignore[attr-defined]
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
    user_id: str = "",
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

    uid = (user_id or "").strip()
    if not uid:
        raise ValueError("user_id 不能为空")

    resolve_weibo_profile_dir(uid)

    image_path: Path | None = None
    if payload.image_url:
        await _emit(on_progress, "下载配图中…")
        image_path = await _download_image(payload.image_url)

    try:
        return await _publish_via_playwright(
            payload,
            user_id=uid,
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
    user_id: str,
    image_path: Path | None,
    on_progress: ProgressCallback | None = None,
) -> tuple[str | None, str | None]:
    from playwright.async_api import async_playwright

    primary_exc: Exception | None = None
    try:
        async with weibo_profile_lock:
            async with async_playwright() as playwright:
                await _emit(on_progress, "启动 Playwright 浏览器…")
                context = await _launch_context(playwright, user_id=user_id)
                pages = context.pages  # type: ignore[attr-defined]
                page = pages[0] if pages else await context.new_page()  # type: ignore[attr-defined]

                try:
                    opened = False
                    for url in _COMPOSE_URLS:
                        try:
                            await _emit(on_progress, f"打开 {url}")
                            await page.goto(
                                url,
                                wait_until="domcontentloaded",
                                timeout=settings.WEIBO_PUBLISH_TIMEOUT_MS,
                            )  # type: ignore[attr-defined]
                            await page.wait_for_timeout(2000)  # type: ignore[attr-defined]
                            opened = True
                            break
                        except Exception:
                            continue
                    if not opened:
                        raise RuntimeError("无法打开微博页面")

                    current_url = page.url  # type: ignore[attr-defined]
                    body = await page.content()  # type: ignore[attr-defined]
                    if not is_likely_logged_in_url(current_url) or any(
                        m in body for m in _LOGIN_MARKERS
                    ):
                        raise RuntimeError(
                            "微博未登录或需要安全验证，请先在 Studio 登录微博或配置 Profile 路径"
                        )

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
                    await _emit(on_progress, "发布完成")
                    return post_url, None
                except Exception as exc:
                    primary_exc = exc
                    logger.warning("Playwright 微博发布失败: %s", exc)
                    shot = _screenshot_dir() / f"weibo_fail_{int(time.time())}.png"
                    try:
                        await page.screenshot(path=str(shot), full_page=True)  # type: ignore[attr-defined]
                    except Exception:
                        pass
                    raise
                finally:
                    await context.close()  # type: ignore[attr-defined]
    except Exception:
        if primary_exc is None:
            raise
        raise RuntimeError(str(primary_exc)) from primary_exc
