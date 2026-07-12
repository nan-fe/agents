"""微博登录会话：Studio 触发 Playwright 打开真实浏览器窗口，用户在浏览器内完成登录。"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field

from app.config import settings
from app.services.social.profile_paths import resolve_weibo_profile_dir
from app.services.social.weibo_auth_store import save_weibo_auth
from app.services.social.weibo_publisher import (
    _LOGIN_MARKERS,
    _launch_context,
    _playwright_profile_lock,
    invalidate_weibo_login_state_cache,
)

logger = logging.getLogger(__name__)

_SESSION_TTL_SEC = 600


@dataclass
class WeiboLoginSession:
    session_id: str
    user_id: str
    playwright: object
    context: object
    page: object
    created_at: float = field(default_factory=time.time)
    _profile_lock_held: bool = field(default=False, repr=False)

    async def evaluate_login(self) -> dict[str, object]:
        url = self.page.url  # type: ignore[attr-defined]
        logged_in = await self.page.evaluate(  # type: ignore[attr-defined]
            """(loginMarkers) => {
                const href = location.href;
                if (!href.includes('weibo.com')) return false;
                if (href.includes('passport.weibo.com')
                    || href.includes('login.sina.com.cn')
                    || href.includes('newlogin')) return false;
                const text = document.body?.innerText || '';
                return !loginMarkers.some((m) => text.includes(m));
            }""",
            list(_LOGIN_MARKERS),
        )
        return {
            "logged_in": logged_in,
            "current_url": url,
            "profile_path": resolve_weibo_profile_dir(self.user_id),
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
        if self._profile_lock_held:
            _playwright_profile_lock.release()
            self._profile_lock_held = False


class WeiboLoginSessionManager:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._sessions: dict[str, WeiboLoginSession] = {}

    async def has_active_session(self, user_id: str | None = None) -> bool:
        async with self._lock:
            if user_id is None:
                return bool(self._sessions)
            uid = user_id.strip()
            return any(session.user_id == uid for session in self._sessions.values())

    async def start(self, *, user_id: str) -> WeiboLoginSession:
        if not settings.WEIBO_PUBLISH_ENABLED:
            raise ValueError("微博发布未启用（WEIBO_PUBLISH_ENABLED=false）")
        if settings.WEIBO_PUBLISH_DRY_RUN:
            raise ValueError("DRY RUN 模式下无需登录")

        uid = (user_id or "").strip()
        if not uid:
            raise ValueError("user_id 不能为空")

        async with self._lock:
            await self._close_all_locked()

            await _playwright_profile_lock.acquire()
            lock_held = True
            try:
                from playwright.async_api import async_playwright

                playwright = await async_playwright().start()
                try:
                    context = await _launch_context(
                        playwright,
                        user_id=uid,
                        headless=False,
                        for_login=True,
                    )
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
                        user_id=uid,
                        playwright=playwright,
                        context=context,
                        page=page,
                        _profile_lock_held=True,
                    )
                    lock_held = False
                    self._sessions[session_id] = session
                    return session
                except Exception:
                    await playwright.stop()
                    raise
            except Exception:
                if lock_held:
                    _playwright_profile_lock.release()
                raise

    async def close(self, session_id: str) -> None:
        async with self._lock:
            await self._close_locked(session_id)

    async def confirm(self, session_id: str) -> dict[str, object]:
        """用户点击「我已登录」：检测登录态，成功则持久化 Profile 并关闭浏览器。"""
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise KeyError("登录会话不存在或已过期")
            if time.time() - session.created_at > _SESSION_TTL_SEC:
                await self._close_locked(session_id)
                raise KeyError("登录会话已过期，请重新开始")

        state = await session.evaluate_login()
        if state["logged_in"]:
            profile_path = str(state["profile_path"])
            current_url = str(state["current_url"])
            await save_weibo_auth(
                user_id=session.user_id,
                profile_path=profile_path,
                logged_in=True,
                current_url=current_url,
            )
            invalidate_weibo_login_state_cache(session.user_id)
            async with self._lock:
                await self._close_locked(session_id)
        return state

    async def _close_all_locked(self) -> None:
        for session_id in list(self._sessions):
            await self._close_locked(session_id)

    async def _close_locked(self, session_id: str) -> None:
        session = self._sessions.pop(session_id, None)
        if session is not None:
            await session.close()


weibo_login_session_manager = WeiboLoginSessionManager()
