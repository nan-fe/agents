"""X OAuth 登录会话：在 Playwright Profile 内完成 OAuth 授权，写入 Web Session Cookie。"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from urllib.parse import parse_qs, urlparse

from app.config import settings
from app.services.social.profile_paths import resolve_x_profile_dir
from app.services.social.x_auth_store import save_x_auth
from app.services.social.x_oauth_service import XOAuthError, x_oauth_service
from app.services.social.x_publisher import (
    _launch_context,
    _page_looks_logged_out,
    _playwright_profile_lock,
    invalidate_x_login_state_cache,
)

logger = logging.getLogger(__name__)

_SESSION_TTL_SEC = 600


@dataclass
class XOAuthLoginSession:
    session_id: str
    user_id: str
    playwright: object
    context: object
    page: object
    created_at: float = field(default_factory=time.time)
    oauth_completed: bool = False
    oauth_error: str | None = None
    x_username: str | None = None
    _profile_lock_held: bool = field(default=False, repr=False)
    _watch_task: asyncio.Task[None] | None = field(default=None, repr=False)

    async def evaluate_profile_login(self) -> dict[str, object]:
        url = self.page.url  # type: ignore[attr-defined]
        lowered = url.lower()
        if (
            "x.com" not in lowered and "twitter.com" not in lowered
        ) or "/social/x/oauth/callback" in lowered:
            await self.page.goto(  # type: ignore[attr-defined]
                "https://x.com/home",
                wait_until="domcontentloaded",
                timeout=settings.X_PUBLISH_TIMEOUT_MS,
            )
            await self.page.wait_for_timeout(2000)  # type: ignore[attr-defined]
            url = self.page.url  # type: ignore[attr-defined]
        body = await self.page.content()  # type: ignore[attr-defined]
        logged_in = not _page_looks_logged_out(body, url)
        return {
            "logged_in": logged_in,
            "current_url": url,
            "profile_path": resolve_x_profile_dir(self.user_id),
            "oauth_completed": self.oauth_completed,
            "x_username": self.x_username,
        }

    async def close(self) -> None:
        if self._watch_task is not None and not self._watch_task.done():
            self._watch_task.cancel()
            try:
                await self._watch_task
            except asyncio.CancelledError:
                pass
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


class XOAuthLoginSessionManager:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._sessions: dict[str, XOAuthLoginSession] = {}

    async def has_active_session(self, user_id: str | None = None) -> bool:
        async with self._lock:
            if user_id is None:
                return bool(self._sessions)
            uid = user_id.strip()
            return any(session.user_id == uid for session in self._sessions.values())

    async def get_session(self, session_id: str) -> XOAuthLoginSession | None:
        async with self._lock:
            return self._sessions.get(session_id)

    async def start(self, *, user_id: str) -> XOAuthLoginSession:
        if not settings.X_PUBLISH_ENABLED:
            raise ValueError("X 发布未启用（X_PUBLISH_ENABLED=false）")
        if settings.X_PUBLISH_DRY_RUN:
            raise ValueError("DRY RUN 模式下无需连接")
        if not x_oauth_service.is_configured():
            raise ValueError("X OAuth 未配置，请设置 X_OAUTH_CLIENT_ID 与 X_OAUTH_CALLBACK_URL")

        uid = (user_id or "").strip()
        if not uid:
            raise ValueError("user_id 不能为空")

        async with self._lock:
            await self._close_all_locked()

            await _playwright_profile_lock.acquire()
            lock_held = True
            try:
                from playwright.async_api import async_playwright

                authorize_url = await x_oauth_service.start_authorize(
                    user_id=uid,
                    return_url=settings.X_OAUTH_CALLBACK_URL,
                )
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
                        authorize_url,
                        wait_until="domcontentloaded",
                        timeout=settings.X_PUBLISH_TIMEOUT_MS,
                    )

                    session_id = uuid.uuid4().hex
                    session = XOAuthLoginSession(
                        session_id=session_id,
                        user_id=uid,
                        playwright=playwright,
                        context=context,
                        page=page,
                        _profile_lock_held=True,
                    )
                    session._watch_task = asyncio.create_task(self._watch_callback(session))
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

    async def confirm(self, session_id: str) -> dict[str, object]:
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise KeyError("OAuth 会话不存在或已过期")
            if time.time() - session.created_at > _SESSION_TTL_SEC:
                await self._close_locked(session_id)
                raise KeyError("OAuth 会话已过期，请重新开始")

        if session.oauth_error:
            raise XOAuthError(session.oauth_error)

        if not session.oauth_completed:
            raise XOAuthError("尚未完成 X OAuth 授权，请在浏览器中登录并授权应用")

        state = await session.evaluate_profile_login()
        if not state["logged_in"]:
            logger.warning(
                "X OAuth confirm 未检测到 Profile 登录态 session=%s url=%s",
                session_id,
                state.get("current_url"),
            )
            raise XOAuthError("OAuth 已完成但浏览器 Profile 未检测到登录态，请重试")

        await save_x_auth(
            user_id=session.user_id,
            profile_path=str(state["profile_path"]),
            logged_in=True,
            current_url=str(state["current_url"]),
        )
        invalidate_x_login_state_cache(session.user_id)
        async with self._lock:
            await self._close_locked(session_id)
        return state

    async def close(self, session_id: str) -> None:
        async with self._lock:
            await self._close_locked(session_id)

    async def _watch_callback(self, session: XOAuthLoginSession) -> None:
        callback_path = "/social/x/oauth/callback"
        deadline = session.created_at + _SESSION_TTL_SEC
        try:
            while time.time() < deadline:
                url = session.page.url  # type: ignore[attr-defined]
                if callback_path not in url:
                    await asyncio.sleep(0.4)
                    continue

                parsed = urlparse(url)
                query = parse_qs(parsed.query)
                if query.get("error"):
                    session.oauth_error = f"X 授权被拒绝: {query['error'][0]}"
                    return

                code = (query.get("code") or [""])[0]
                state = (query.get("state") or [""])[0]
                if not code or not state:
                    await asyncio.sleep(0.4)
                    continue

                try:
                    username = await x_oauth_service.complete_callback(code, state)
                    session.oauth_completed = True
                    session.x_username = username
                    invalidate_x_login_state_cache(session.user_id)
                    try:
                        await session.page.goto(  # type: ignore[attr-defined]
                            "https://x.com/home",
                            wait_until="domcontentloaded",
                            timeout=settings.X_PUBLISH_TIMEOUT_MS,
                        )
                        await session.page.wait_for_timeout(2000)  # type: ignore[attr-defined]
                    except Exception as exc:
                        logger.warning("OAuth 成功后跳转 X 首页失败: %s", exc)
                        try:
                            await session.page.set_content(  # type: ignore[attr-defined]
                                "<html><body><h2>X 授权成功</h2>"
                                "<p>请返回 Studio 并点击「我已完成授权」。</p></body></html>"
                            )
                        except Exception:
                            pass
                    return
                except XOAuthError as exc:
                    session.oauth_error = str(exc)
                    return
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("X OAuth 回调监听失败: %s", exc)
            session.oauth_error = str(exc)

    async def _close_all_locked(self) -> None:
        for session_id in list(self._sessions):
            await self._close_locked(session_id)

    async def _close_locked(self, session_id: str) -> None:
        session = self._sessions.pop(session_id, None)
        if session is not None:
            await session.close()


x_oauth_login_session_manager = XOAuthLoginSessionManager()
