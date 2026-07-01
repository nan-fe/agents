"""微博可视化登录会话：Studio 内通过 browser-use 截图 + 点击/输入完成登录。"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field

from app.config import settings
from app.services.social.browser_use_support import (
    click_page,
    close_weibo_browser_session,
    create_weibo_browser_session,
    get_focus_page_html,
    get_focus_page_url,
    navigate_weibo_home,
    press_page_key,
    require_browser_use,
    screenshot_page_png,
    type_on_page,
)
from app.services.social.content_adapter import is_likely_logged_in_url
from app.services.social.profile_paths import resolve_weibo_profile_dir
from app.services.social.weibo_publisher import _LOGIN_MARKERS

logger = logging.getLogger(__name__)

_SESSION_TTL_SEC = 600


@dataclass
class WeiboLoginSession:
    session_id: str
    browser_session: object
    created_at: float = field(default_factory=time.time)

    async def screenshot_png(self) -> bytes:
        return await screenshot_page_png(self.browser_session)  # type: ignore[arg-type]

    async def click(self, x: float, y: float) -> None:
        await click_page(self.browser_session, x, y)  # type: ignore[arg-type]

    async def type_text(self, text: str) -> None:
        await type_on_page(self.browser_session, text)  # type: ignore[arg-type]

    async def press_key(self, key: str) -> None:
        await press_page_key(self.browser_session, key)  # type: ignore[arg-type]

    async def evaluate_login(self) -> dict[str, object]:
        browser_session = self.browser_session
        url = await get_focus_page_url(browser_session)  # type: ignore[arg-type]
        body = await get_focus_page_html(browser_session)  # type: ignore[arg-type]
        logged_in = is_likely_logged_in_url(url) and not any(m in body for m in _LOGIN_MARKERS)
        return {
            "logged_in": logged_in,
            "current_url": url,
            "profile_path": resolve_weibo_profile_dir(),
        }

    async def close(self) -> None:
        await close_weibo_browser_session(self.browser_session)  # type: ignore[arg-type]


class WeiboLoginSessionManager:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._sessions: dict[str, WeiboLoginSession] = {}

    async def start(self) -> WeiboLoginSession:
        if not settings.WEIBO_PUBLISH_ENABLED:
            raise ValueError("微博发布未启用（WEIBO_PUBLISH_ENABLED=false）")
        if settings.WEIBO_PUBLISH_DRY_RUN:
            raise ValueError("DRY RUN 模式下无需登录")

        require_browser_use()

        async with self._lock:
            await self._close_all_locked()

            browser_session = await create_weibo_browser_session(headless=True)
            try:
                await navigate_weibo_home(browser_session)

                session_id = uuid.uuid4().hex
                session = WeiboLoginSession(
                    session_id=session_id,
                    browser_session=browser_session,
                )
                self._sessions[session_id] = session
                return session
            except Exception:
                await close_weibo_browser_session(browser_session)
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
