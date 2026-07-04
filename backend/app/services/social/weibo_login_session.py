"""微博可视化登录会话：Studio 内通过 Playwright 截图 + 点击/输入完成登录。"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field

from app.config import settings
from app.services.social.content_adapter import is_likely_logged_in_url
from app.services.social.profile_paths import resolve_weibo_profile_dir
from app.services.social.weibo_publisher import (
    _LOGIN_MARKERS,
    _launch_context,
    _playwright_profile_lock,
)

logger = logging.getLogger(__name__)

_SESSION_TTL_SEC = 600


@dataclass
class WeiboLoginSession:
    session_id: str
    playwright: object
    context: object
    page: object
    created_at: float = field(default_factory=time.time)

    async def screenshot_png(self) -> bytes:
        return await self.page.screenshot(full_page=False, type="png")  # type: ignore[attr-defined]

    async def click(self, x: float, y: float) -> None:
        await self.page.mouse.click(int(x), int(y))  # type: ignore[attr-defined]
        await asyncio.sleep(0.4)

    async def type_text(self, text: str) -> None:
        await self.page.keyboard.insert_text(text)  # type: ignore[attr-defined]

    async def press_key(self, key: str) -> None:
        await self.page.keyboard.press(key)  # type: ignore[attr-defined]

    async def evaluate_login(self) -> dict[str, object]:
        url = self.page.url  # type: ignore[attr-defined]
        body = await self.page.content()  # type: ignore[attr-defined]
        logged_in = is_likely_logged_in_url(url) and not any(m in body for m in _LOGIN_MARKERS)
        return {
            "logged_in": logged_in,
            "current_url": url,
            "profile_path": resolve_weibo_profile_dir(),
        }

    async def close(self) -> None:
        try:
            await self.context.close()  # type: ignore[attr-defined]
        except Exception as exc:
            logger.debug("关闭 Playwright context 失败: %s", exc)
        try:
            await self.playwright.stop()  # type: ignore[attr-defined]
        except Exception as exc:
            logger.debug("关闭 Playwright 失败: %s", exc)


class WeiboLoginSessionManager:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._sessions: dict[str, WeiboLoginSession] = {}

    async def start(self) -> WeiboLoginSession:
        if not settings.WEIBO_PUBLISH_ENABLED:
            raise ValueError("微博发布未启用（WEIBO_PUBLISH_ENABLED=false）")
        if settings.WEIBO_PUBLISH_DRY_RUN:
            raise ValueError("DRY RUN 模式下无需登录")

        async with self._lock:
            await self._close_all_locked()

            async with _playwright_profile_lock:
                from playwright.async_api import async_playwright

                playwright = await async_playwright().start()
                try:
                    context = await _launch_context(playwright)
                    pages = context.pages  # type: ignore[attr-defined]
                    page = pages[0] if pages else await context.new_page()  # type: ignore[attr-defined]
                    await page.goto(  # type: ignore[attr-defined]
                        "https://weibo.com/",
                        wait_until="domcontentloaded",
                        timeout=settings.WEIBO_PUBLISH_TIMEOUT_MS,
                    )
                    await page.wait_for_timeout(1200)  # type: ignore[attr-defined]

                    session_id = uuid.uuid4().hex
                    session = WeiboLoginSession(
                        session_id=session_id,
                        playwright=playwright,
                        context=context,
                        page=page,
                    )
                    self._sessions[session_id] = session
                    return session
                except Exception:
                    await playwright.stop()
                    raise

    async def get(self, session_id: str) -> WeiboLoginSession:
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise KeyError("登录会话不存在或已过期")
            if time.time() - session.created_at > _SESSION_TTL_SEC:
                await self._close_locked(session_id)
                raise KeyError("登录会话已过期，请重新开始")
            return session

    async def close(self, session_id: str) -> None:
        async with self._lock:
            await self._close_locked(session_id)

    async def _close_all_locked(self) -> None:
        for session_id in list(self._sessions):
            await self._close_locked(session_id)

    async def _close_locked(self, session_id: str) -> None:
        session = self._sessions.pop(session_id, None)
        if session is not None:
            await session.close()


weibo_login_session_manager = WeiboLoginSessionManager()
