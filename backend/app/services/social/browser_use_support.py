"""browser-use 浏览器会话共享工具（微博 Profile / 登录 / 发布）。"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from app.services.social.profile_paths import resolve_weibo_profile_dir

if TYPE_CHECKING:
    from browser_use.browser.session import BrowserSession

logger = logging.getLogger(__name__)

_weibo_browser_lock = asyncio.Lock()

VIEWPORT_WIDTH = 1280
VIEWPORT_HEIGHT = 900

_WEIBO_ALLOWED_DOMAINS = ["*.weibo.com", "weibo.com"]


def require_browser_use() -> Any:
    try:
        from browser_use import BrowserSession
    except ImportError as exc:
        raise RuntimeError(
            "browser-use 未安装。请执行："
            'pip install "browser-use>=0.12.0" -i https://pypi.org/simple'
        ) from exc
    return BrowserSession


async def create_weibo_browser_session(*, headless: bool) -> BrowserSession:
    """启动与发微博相同的 browser-use 本地会话（复用 user_data_dir）。"""
    async with _weibo_browser_lock:
        BrowserSession = require_browser_use()
        profile_dir = resolve_weibo_profile_dir()
        session = BrowserSession(
            headless=headless,
            user_data_dir=profile_dir,
            allowed_domains=_WEIBO_ALLOWED_DOMAINS,
            enable_default_extensions=False,
            viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT},
        )
        await session.start()
        return session


async def close_weibo_browser_session(session: BrowserSession) -> None:
    """关闭 browser-use 会话并持久化 Cookie/Storage。"""
    try:
        await session.kill()
    except Exception as exc:
        logger.debug("关闭 browser-use 会话失败: %s", exc)


async def navigate_weibo_home(session: BrowserSession) -> None:
    await session.navigate_to("https://weibo.com/")
    await asyncio.sleep(1.2)


async def get_focus_page_html(session: BrowserSession) -> str:
    page = await session.must_get_current_page()
    return await page.evaluate("() => document.documentElement.outerHTML")


async def get_focus_page_url(session: BrowserSession) -> str:
    page = await session.must_get_current_page()
    return await page.get_url()


async def click_page(session: BrowserSession, x: float, y: float) -> None:
    page = await session.must_get_current_page()
    mouse = await page.mouse
    await mouse.click(int(x), int(y))
    await asyncio.sleep(0.4)


async def type_on_page(session: BrowserSession, text: str) -> None:
    cdp_session = await session.get_or_create_cdp_session(target_id=None, focus=False)
    if cdp_session is None:
        raise RuntimeError("browser-use 无可用 CDP 会话")
    await cdp_session.cdp_client.send.Input.insertText(
        params={"text": text},
        session_id=cdp_session.session_id,
    )


async def press_page_key(session: BrowserSession, key: str) -> None:
    page = await session.must_get_current_page()
    await page.press(key)


async def screenshot_page_png(session: BrowserSession) -> bytes:
    return await session.take_screenshot(full_page=False, format="png")
