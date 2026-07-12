"""X Playwright 发布实现（Profile 浏览器模拟人工发帖）。"""

from __future__ import annotations

import asyncio
import logging
import sys
import tempfile
import time
from pathlib import Path
from typing import Awaitable, Callable
from urllib.parse import quote, urlparse

import httpx

from app.config import settings
from app.services.social.content_adapter import XPublishPayload
from app.services.social.profile_paths import (
    clear_stale_chromium_profile_lock,
    resolve_x_profile_dir,
    x_profile_lock,
)
from app.services.social.x_auth_store import get_x_auth

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str], Awaitable[None] | None]

_login_state_cache: dict[str, tuple[float, dict[str, object]]] = {}
_LOGIN_STATE_CACHE_TTL_SEC = 300
_login_check_lock = asyncio.Lock()
_playwright_profile_lock = x_profile_lock

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

_COMPOSE_URLS = (
    "https://x.com/compose/post",
    "https://x.com/home",
)

_COMPOSE_INTENT_URL = "https://x.com/intent/post"

_TEXTAREA_SELECTORS = (
    "[data-testid='tweetTextarea_0']",
    "div[contenteditable='true'][data-testid='tweetTextarea_0']",
    "div[role='textbox'][data-testid='tweetTextarea_0']",
)

_PUBLISH_BUTTON_SELECTORS = (
    "[data-testid='tweetButton']",
    "[data-testid='tweetButtonInline']",
    "button:has-text('Post')",
    "button:has-text('发帖')",
)

_COMPOSE_TRIGGER_TEXTS = (
    "What's happening?",
    "有什么新鲜事",
)

_COMPOSE_OPEN_SELECTORS = (
    "[data-testid='SideNav_NewTweet_Button']",
    "a[href='/compose/post']",
    "a[href='/compose/tweet']",
)

_LOGIN_MARKERS = (
    "Sign in to X",
    "Log in to X",
    "Create your account",
    "Sign up",
    "登录",
    "注册",
)


def invalidate_x_login_state_cache(user_id: str = "") -> None:
    uid = (user_id or "").strip()
    if uid:
        _login_state_cache.pop(uid, None)
    else:
        _login_state_cache.clear()


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


def _is_login_url(url: str) -> bool:
    lowered = url.lower()
    # 后端 OAuth 回调页不是 X 登录页
    if "/social/x/oauth/callback" in lowered:
        return False
    return any(
        token in lowered
        for token in (
            "/login",
            "/i/flow/login",
            "signin",
            "/i/oauth2/authorize",
            "account/access",
        )
    )


def _page_looks_logged_out(body: str, url: str) -> bool:
    if _is_login_url(url):
        return True
    return any(marker in body for marker in _LOGIN_MARKERS)


async def _check_x_login_state_playwright(user_id: str) -> dict[str, object]:
    from playwright.async_api import async_playwright

    profile_dir = resolve_x_profile_dir(user_id)
    async with x_profile_lock:
        async with async_playwright() as playwright:
            context = await _launch_context(playwright, user_id=user_id, headless=True)
            pages = context.pages  # type: ignore[attr-defined]
            page = pages[0] if pages else await context.new_page()  # type: ignore[attr-defined]
            await page.goto(
                "https://x.com/home",
                wait_until="domcontentloaded",
                timeout=settings.X_PUBLISH_TIMEOUT_MS,
            )  # type: ignore[attr-defined]
            await page.wait_for_timeout(2000)  # type: ignore[attr-defined]
            url = page.url  # type: ignore[attr-defined]
            body = await page.content()  # type: ignore[attr-defined]
            logged_in = not _page_looks_logged_out(body, url)
            await context.close()  # type: ignore[attr-defined]
            return {
                "configured": True,
                "logged_in": logged_in,
                "current_url": url,
                "profile_path": profile_dir,
                "driver": "playwright",
            }


async def check_x_login_state(*, user_id: str, force_refresh: bool = False) -> dict[str, object]:
    """检测 X 登录态。默认走缓存/DB；force_refresh 才启动浏览器验证。"""
    uid = (user_id or "").strip()
    if not uid:
        return {"configured": False, "logged_in": False, "reason": "user_id 不能为空"}

    if not settings.X_PUBLISH_ENABLED:
        return {"configured": False, "logged_in": False, "reason": "未启用 X 发布"}
    if settings.X_PUBLISH_DRY_RUN:
        return {"configured": True, "logged_in": True, "dry_run": True}

    profile_dir = resolve_x_profile_dir(uid)

    stored = await get_x_auth(uid)
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
            result = await _check_x_login_state_playwright(uid)
            result["user_id"] = uid
            if result.get("logged_in"):
                from app.services.social.x_auth_store import save_x_auth

                await save_x_auth(
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
            logger.warning("X 登录态检测失败 user_id=%s: %s", uid, exc)
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


def format_x_browser_error(exc: BaseException) -> str:
    message = str(exc)
    if is_chromium_profile_lock_error(exc):
        return (
            "X 浏览器 Profile 被占用，请稍后重试；"
            "若持续失败，请联系管理员清理 Profile 目录中的锁文件"
        )
    if "executable doesn't exist" in message.lower():
        return "服务器未安装 Playwright Chromium，请联系管理员执行 playwright install chromium"
    first_line = message.splitlines()[0].strip()
    if len(first_line) > 240:
        return first_line[:240] + "…"
    return first_line or "无法启动 X 登录浏览器"


async def _launch_context(
    playwright: object,
    *,
    user_id: str,
    headless: bool | None = None,
    for_login: bool = False,
) -> object:
    profile_dir = resolve_x_profile_dir(user_id)
    resolved_headless = settings.X_PUBLISH_HEADLESS if headless is None else headless
    channel = (settings.X_BROWSER_CHANNEL or settings.WEIBO_BROWSER_CHANNEL or "").strip()

    launch_kwargs: dict = {
        "headless": resolved_headless,
        "user_data_dir": profile_dir,
        "args": list(_CHROMIUM_STEALTH_ARGS),
        "ignore_default_args": ["--enable-automation"],
        "locale": "en-US",
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
            logger.warning("检测到过期 X Profile 锁，清理后重试启动浏览器")
            return await chromium.launch_persistent_context(**kwargs)

    try:
        context = await _try_launch(launch_kwargs)
    except Exception as exc:
        if not channel:
            raise
        logger.warning(
            "无法用 channel=%s 启动 X 浏览器，回退到 Playwright Chromium: %s",
            channel,
            exc,
        )
        fallback_kwargs = {k: v for k, v in launch_kwargs.items() if k != "channel"}
        context = await _try_launch(fallback_kwargs)

    await context.add_init_script(_STEALTH_INIT_SCRIPT)  # type: ignore[attr-defined]
    return context


def _select_all_shortcut() -> str:
    return "Meta+a" if sys.platform == "darwin" else "Control+a"


def _compose_intent_url(text: str) -> str:
    return f"{_COMPOSE_INTENT_URL}?text={quote(text, safe='')}"


def _post_shortcut() -> str:
    return "Meta+Enter" if sys.platform == "darwin" else "Control+Enter"


async def _open_compose_with_text(page: object, text: str) -> bool:
    try:
        await page.goto(  # type: ignore[attr-defined]
            _compose_intent_url(text),
            wait_until="domcontentloaded",
            timeout=settings.X_PUBLISH_TIMEOUT_MS,
        )
        await page.wait_for_timeout(2500)  # type: ignore[attr-defined]
        return await _visible_compose_locator(page) is not None
    except Exception:
        return False


async def _open_compose_page(page: object) -> bool:
    for url in _COMPOSE_URLS:
        try:
            await page.goto(  # type: ignore[attr-defined]
                url,
                wait_until="domcontentloaded",
                timeout=settings.X_PUBLISH_TIMEOUT_MS,
            )
            await page.wait_for_timeout(2500)  # type: ignore[attr-defined]
            return True
        except Exception:
            continue
    return False


async def _compose_over_limit(page: object) -> bool:
    try:
        return bool(
            await page.evaluate(  # type: ignore[attr-defined]
                """() => {
                    for (const node of document.querySelectorAll('span')) {
                        const text = (node.textContent || '').trim();
                        if (/^-\\d+$/.test(text)) return true;
                    }
                    return false;
                }"""
            )
        )
    except Exception:
        return False


async def _enabled_publish_button(page: object, *, timeout_ms: int = 15000) -> object | None:
    deadline = time.time() + timeout_ms / 1000.0
    while time.time() < deadline:
        for selector in _PUBLISH_BUTTON_SELECTORS:
            try:
                buttons = page.locator(f"{selector}:not([disabled])")  # type: ignore[attr-defined]
                count = await buttons.count()
                for index in range(count - 1, -1, -1):
                    btn = buttons.nth(index)
                    if not await btn.is_visible():
                        continue
                    if await btn.is_enabled():
                        return btn
            except Exception:
                continue
        await page.wait_for_timeout(300)  # type: ignore[attr-defined]
    return None


async def _wait_for_media_ready(page: object, *, timeout_ms: int = 20000) -> None:
    deadline = time.time() + timeout_ms / 1000.0
    while time.time() < deadline:
        try:
            progress = page.locator("[role='progressbar']")  # type: ignore[attr-defined]
            if await progress.count() == 0:
                return
            visible = False
            for index in range(await progress.count()):
                if await progress.nth(index).is_visible():
                    visible = True
                    break
            if not visible:
                return
        except Exception:
            return
        await page.wait_for_timeout(500)  # type: ignore[attr-defined]


async def _visible_compose_locator(page: object) -> object | None:
    for selector in _TEXTAREA_SELECTORS:
        try:
            locator = page.locator(selector).first  # type: ignore[attr-defined]
            if await locator.count() == 0:
                continue
            await locator.wait_for(state="visible", timeout=4000)  # type: ignore[attr-defined]
            return locator
        except Exception:
            continue

    try:
        textbox = page.get_by_role("textbox").first  # type: ignore[attr-defined]
        if await textbox.count() > 0:
            await textbox.wait_for(state="visible", timeout=4000)  # type: ignore[attr-defined]
            return textbox
    except Exception:
        pass

    try:
        editable = page.locator("div[contenteditable='true']").first  # type: ignore[attr-defined]
        if await editable.count() > 0:
            await editable.wait_for(state="visible", timeout=4000)  # type: ignore[attr-defined]
            return editable
    except Exception:
        pass

    return None


async def _open_compose_surface(page: object) -> None:
    for text in _COMPOSE_TRIGGER_TEXTS:
        try:
            trigger = page.get_by_text(text, exact=False).first  # type: ignore[attr-defined]
            if await trigger.count() > 0:
                await trigger.click(timeout=4000)
                await page.wait_for_timeout(1000)  # type: ignore[attr-defined]
                return
        except Exception:
            continue

    for selector in _COMPOSE_OPEN_SELECTORS:
        try:
            opener = page.locator(selector).first  # type: ignore[attr-defined]
            if await opener.count() == 0:
                continue
            await opener.click(timeout=4000)
            await page.wait_for_timeout(1200)  # type: ignore[attr-defined]
            return
        except Exception:
            continue


async def _type_into_compose(page: object, locator: object, text: str) -> bool:
    try:
        await locator.click(timeout=5000)  # type: ignore[attr-defined]
        await page.wait_for_timeout(300)  # type: ignore[attr-defined]
        await page.keyboard.press(_select_all_shortcut())  # type: ignore[attr-defined]
        await page.keyboard.press("Backspace")  # type: ignore[attr-defined]
        await page.keyboard.insert_text(text)  # type: ignore[attr-defined]
        return True
    except Exception:
        try:
            await locator.click(timeout=4000)  # type: ignore[attr-defined]
            await locator.press_sequentially(text, delay=6)  # type: ignore[attr-defined]
            return True
        except Exception:
            return False


async def _fill_compose(page: object, text: str) -> bool:
    locator = await _visible_compose_locator(page)
    if locator is None:
        await _open_compose_surface(page)
        locator = await _visible_compose_locator(page)
    if locator is None:
        return False
    return await _type_into_compose(page, locator, text)


async def _click_publish(page: object) -> bool:
    if await _compose_over_limit(page):
        return False

    btn = await _enabled_publish_button(page)
    if btn is not None:
        try:
            await btn.scroll_into_view_if_needed(timeout=3000)  # type: ignore[attr-defined]
            await btn.click(timeout=8000)  # type: ignore[attr-defined]
            return True
        except Exception:
            try:
                await btn.click(timeout=8000, force=True)  # type: ignore[attr-defined]
                return True
            except Exception:
                pass

    for selector in _PUBLISH_BUTTON_SELECTORS:
        try:
            btn = page.locator(selector).last  # type: ignore[attr-defined]
            if await btn.count() == 0:
                continue
            await btn.click(timeout=5000)
            return True
        except Exception:
            continue

    try:
        await page.keyboard.press(_post_shortcut())  # type: ignore[attr-defined]
        await page.wait_for_timeout(1500)  # type: ignore[attr-defined]
        return True
    except Exception:
        return False


async def _upload_image(page: object, image_path: Path) -> bool:
    selectors = (
        "input[data-testid='fileInput']",
        "input[type='file'][accept*='image']",
        "input[type='file']",
    )
    for selector in selectors:
        try:
            inp = page.locator(selector).first  # type: ignore[attr-defined]
            if await inp.count() == 0:
                continue
            await inp.set_input_files(str(image_path), timeout=15000)
            await page.wait_for_timeout(2500)  # type: ignore[attr-defined]
            return True
        except Exception:
            continue
    return False


async def publish_to_x(
    payload: XPublishPayload,
    *,
    user_id: str,
    on_progress: ProgressCallback | None = None,
) -> tuple[str | None, str | None]:
    """
    通过 Playwright Profile 发布到 X。

    Returns:
        (post_url, screenshot_path_on_failure)
    """
    if settings.X_PUBLISH_DRY_RUN:
        await _emit(on_progress, "DRY RUN：模拟发布成功")
        return "https://x.com/i/web/status/dry-run", None

    if not settings.X_PUBLISH_ENABLED:
        raise ValueError("X 发布未启用（X_PUBLISH_ENABLED=false）")

    if not payload.text.strip():
        raise ValueError("发布正文不能为空")

    uid = (user_id or "").strip()
    if not uid:
        raise ValueError("user_id 不能为空")

    resolve_x_profile_dir(uid)

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
    payload: XPublishPayload,
    *,
    user_id: str,
    image_path: Path | None,
    on_progress: ProgressCallback | None = None,
) -> tuple[str | None, str | None]:
    from playwright.async_api import async_playwright

    primary_exc: Exception | None = None
    try:
        async with x_profile_lock:
            async with async_playwright() as playwright:
                await _emit(on_progress, "启动 Playwright 浏览器…")
                context = await _launch_context(
                    playwright,
                    user_id=user_id,
                    headless=settings.X_PUBLISH_HEADLESS,
                )
                page = await context.new_page()  # type: ignore[attr-defined]
                try:
                    await page.bring_to_front()  # type: ignore[attr-defined]
                except Exception:
                    pass

                try:
                    await _emit(on_progress, "打开发帖页…")
                    composed = await _open_compose_with_text(page, payload.text)
                    if not composed:
                        if not await _open_compose_page(page):
                            raise RuntimeError("无法打开 X 页面")
                        await _emit(on_progress, "填写正文…")
                        filled = await _fill_compose(page, payload.text)
                        if not filled:
                            raise RuntimeError("未找到 X 发帖编辑器")

                    current_url = page.url  # type: ignore[attr-defined]
                    body = await page.content()  # type: ignore[attr-defined]
                    if _page_looks_logged_out(body, current_url):
                        raise RuntimeError("X 未登录，请先在 Studio 连接 X 账号")

                    if image_path is not None:
                        await _emit(on_progress, "上传配图…")
                        uploaded = await _upload_image(page, image_path)
                        if not uploaded:
                            await _emit(on_progress, "配图上传失败，继续纯文本发布")
                        else:
                            await _wait_for_media_ready(page)

                    if await _compose_over_limit(page):
                        raise RuntimeError("正文超出 X 280 字符限制，发布按钮不可用")

                    await _emit(on_progress, "点击发布…")
                    published = await _click_publish(page)
                    if not published:
                        if await _compose_over_limit(page):
                            raise RuntimeError("正文超出 X 280 字符限制，发布按钮不可用")
                        raise RuntimeError("未找到可点击的发布按钮")

                    await page.wait_for_timeout(4000)  # type: ignore[attr-defined]
                    post_url = page.url  # type: ignore[attr-defined]
                    if _is_login_url(post_url):
                        raise RuntimeError("发布后仍停留在登录页，可能未成功发帖")
                    await _emit(on_progress, "发布完成")
                    return post_url, None
                except Exception as exc:
                    primary_exc = exc
                    logger.warning("Playwright X 发布失败: %s", exc)
                    shot = _screenshot_dir() / f"x_fail_{int(time.time())}.png"
                    try:
                        await page.screenshot(path=str(shot), full_page=True)  # type: ignore[attr-defined]
                    except Exception:
                        shot = None  # type: ignore[assignment]
                    raise
                finally:
                    await context.close()  # type: ignore[attr-defined]
    except Exception:
        if primary_exc is None:
            raise
        raise RuntimeError(str(primary_exc)) from primary_exc
