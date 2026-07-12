"""X 手动登录会话（OAuth 未配置时的 fallback）。"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field

from app.config import settings
from app.services.social.browser_display import resolve_login_headless
from app.services.social.profile_paths import resolve_x_profile_dir
from app.services.social.x_auth_store import save_x_auth
from app.services.social.x_publisher import (
    _LOGIN_MARKERS,
    _is_login_url,
    _launch_context,
    _playwright_profile_lock,
    invalidate_x_login_state_cache,
)

logger = logging.getLogger(__name__)

_SESSION_TTL_SEC = 600


@dataclass
class XLoginSession:
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
                if (href.includes('/login') || href.includes('/i/flow/login')
                    || href.includes('signin') || href.includes('oauth')) {
                    return false;
                }
                if (!href.includes('x.com') && !href.includes('twitter.com')) return false;
                const text = document.body?.innerText || '';
                return !loginMarkers.some((m) => text.includes(m));
            }""",
            list(_LOGIN_MARKERS),
        )
        if _is_login_url(url):
            logged_in = False
        return {
            "logged_in": logged_in,
            "current_url": url,
            "profile_path": resolve_x_profile_dir(self.user_id),
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


class XLoginSessionManager:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._sessions: dict[str, XLoginSession] = {}

    async def has_active_session(self, user_id: str | None = None) -> bool:
        async with self._lock:
            if user_id is None:
                return bool(self._sessions)
            uid = user_id.strip()
            return any(session.user_id == uid for session in self._sessions.values())

    async def start(self, *, user_id: str) -> XLoginSession:
        if not settings.X_PUBLISH_ENABLED:
            raise ValueError("X 发布未启用（X_PUBLISH_ENABLED=false）")
        if settings.X_PUBLISH_DRY_RUN:
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
                        headless=resolve_login_headless(explicit=False),
                        for_login=True,
                    )
                    pages = context.pages  # type: ignore[attr-defined]
                    page = pages[0] if pages else await context.new_page()  # type: ignore[attr-defined]
                    await page.goto(  # type: ignore[attr-defined]
                        "https://x.com/i/flow/login",
                        wait_until="domcontentloaded",
                        timeout=settings.X_PUBLISH_TIMEOUT_MS,
                    )
                    await page.wait_for_timeout(1500)  # type: ignore[attr-defined]

                    session_id = uuid.uuid4().hex
                    session = XLoginSession(
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
            await save_x_auth(
                user_id=session.user_id,
                profile_path=profile_path,
                logged_in=True,
                current_url=current_url,
            )
            invalidate_x_login_state_cache(session.user_id)
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


x_login_session_manager = XLoginSessionManager()
