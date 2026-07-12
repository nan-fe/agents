"""X 可视化登录 API 测试。"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app
from app.memory.db import close_db, init_db
from app.services.social.x_login_session import XLoginSession
from app.services.social.x_oauth_login_session import XOAuthLoginSession


@pytest.fixture(autouse=True)
def memory_db(monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_URL", "sqlite+aiosqlite:///:memory:")


def _mock_login_session(*, logged_in: bool = False) -> XLoginSession:
    session = XLoginSession(
        session_id="test-x-session",
        user_id="demo-user",
        playwright=MagicMock(),
        context=MagicMock(),
        page=MagicMock(),
    )
    session.evaluate_login = AsyncMock(  # type: ignore[method-assign]
        return_value={
            "logged_in": logged_in,
            "current_url": "https://x.com/home" if logged_in else "https://x.com/i/flow/login",
            "profile_path": "/tmp/x-profile",
        },
    )
    session.close = AsyncMock()  # type: ignore[method-assign]
    return session


def _mock_oauth_session(
    *, logged_in: bool = True, oauth_completed: bool = True
) -> XOAuthLoginSession:
    session = XOAuthLoginSession(
        session_id="test-oauth-session",
        user_id="demo-user",
        playwright=MagicMock(),
        context=MagicMock(),
        page=MagicMock(),
        oauth_completed=oauth_completed,
        x_username="demo",
    )
    session.evaluate_profile_login = AsyncMock(  # type: ignore[method-assign]
        return_value={
            "logged_in": logged_in,
            "current_url": "https://x.com/home",
            "profile_path": "/tmp/x-profile",
            "oauth_completed": oauth_completed,
            "x_username": "demo",
        },
    )
    session.close = AsyncMock()  # type: ignore[method-assign]
    return session


def test_x_login_api_flow() -> None:
    async def _run() -> None:
        await close_db()
        await init_db()

        prev_enabled = settings.X_PUBLISH_ENABLED
        prev_dry = settings.X_PUBLISH_DRY_RUN
        settings.X_PUBLISH_ENABLED = True
        settings.X_PUBLISH_DRY_RUN = False

        session = _mock_login_session(logged_in=False)
        logged_in_state = {
            "logged_in": True,
            "current_url": "https://x.com/home",
            "profile_path": "/tmp/x-profile",
        }

        transport = ASGITransport(app=app)
        with patch(
            "app.main.x_login_session_manager.start",
            AsyncMock(return_value=session),
        ):
            with patch(
                "app.main.x_login_session_manager.confirm",
                AsyncMock(return_value=logged_in_state),
            ):
                with patch(
                    "app.main.x_login_session_manager.close",
                    AsyncMock(),
                ):
                    async with AsyncClient(transport=transport, base_url="http://test") as client:
                        start_resp = await client.post(
                            "/social/x/login/start",
                            json={"user_id": "demo-user"},
                        )
                        assert start_resp.status_code == 200
                        body = start_resp.json()
                        assert body["session_id"] == "test-x-session"
                        assert body["logged_in"] is False

                        confirm_resp = await client.post(
                            "/social/x/login/test-x-session/confirm",
                        )
                        assert confirm_resp.status_code == 200
                        assert confirm_resp.json()["logged_in"] is True

        settings.X_PUBLISH_ENABLED = prev_enabled
        settings.X_PUBLISH_DRY_RUN = prev_dry
        await close_db()

    asyncio.run(_run())


def test_x_oauth_api_flow() -> None:
    async def _run() -> None:
        await close_db()
        await init_db()

        prev_enabled = settings.X_PUBLISH_ENABLED
        prev_dry = settings.X_PUBLISH_DRY_RUN
        prev_client = settings.X_OAUTH_CLIENT_ID
        prev_callback = settings.X_OAUTH_CALLBACK_URL
        settings.X_PUBLISH_ENABLED = True
        settings.X_PUBLISH_DRY_RUN = False
        settings.X_OAUTH_CLIENT_ID = "test-client"
        settings.X_OAUTH_CALLBACK_URL = "http://localhost:8000/social/x/oauth/callback"

        session = _mock_oauth_session()
        confirm_state = {
            "logged_in": True,
            "current_url": "https://x.com/home",
            "profile_path": "/tmp/x-profile",
        }

        transport = ASGITransport(app=app)
        with patch(
            "app.main.x_oauth_login_session_manager.start",
            AsyncMock(return_value=session),
        ):
            with patch(
                "app.main.x_oauth_login_session_manager.get_session",
                AsyncMock(return_value=session),
            ):
                with patch(
                    "app.main.x_oauth_login_session_manager.confirm",
                    AsyncMock(return_value=confirm_state),
                ):
                    async with AsyncClient(transport=transport, base_url="http://test") as client:
                        start_resp = await client.post(
                            "/social/x/oauth/start",
                            json={"user_id": "demo-user"},
                        )
                        assert start_resp.status_code == 200
                        body = start_resp.json()
                        assert body["session_id"] == "test-oauth-session"
                        assert body["oauth_completed"] is True
                        assert body["x_username"] == "demo"

                        status_resp = await client.get(
                            "/social/x/oauth/session/test-oauth-session",
                        )
                        assert status_resp.status_code == 200

                        confirm_resp = await client.post(
                            "/social/x/oauth/session/test-oauth-session/confirm",
                        )
                        assert confirm_resp.status_code == 200
                        assert confirm_resp.json()["logged_in"] is True

        settings.X_PUBLISH_ENABLED = prev_enabled
        settings.X_PUBLISH_DRY_RUN = prev_dry
        settings.X_OAUTH_CLIENT_ID = prev_client
        settings.X_OAUTH_CALLBACK_URL = prev_callback
        await close_db()

    asyncio.run(_run())


def test_x_oauth_browserless_start() -> None:
    async def _run() -> None:
        await close_db()
        await init_db()

        prev_enabled = settings.X_PUBLISH_ENABLED
        prev_dry = settings.X_PUBLISH_DRY_RUN
        prev_client = settings.X_OAUTH_CLIENT_ID
        prev_callback = settings.X_OAUTH_CALLBACK_URL
        settings.X_PUBLISH_ENABLED = True
        settings.X_PUBLISH_DRY_RUN = False
        settings.X_OAUTH_CLIENT_ID = "test-client"
        settings.X_OAUTH_CALLBACK_URL = "http://localhost:8000/social/x/oauth/callback"

        transport = ASGITransport(app=app)
        with patch(
            "app.services.social.x_oauth_login_session.use_browserless_oauth",
            return_value=True,
        ):
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                start_resp = await client.post(
                    "/social/x/oauth/start",
                    json={"user_id": "demo-user"},
                )
                assert start_resp.status_code == 200
                body = start_resp.json()
                assert body["browserless"] is True
                assert body["authorize_url"].startswith("https://twitter.com/i/oauth2/authorize")
                assert body["oauth_completed"] is False

        settings.X_PUBLISH_ENABLED = prev_enabled
        settings.X_PUBLISH_DRY_RUN = prev_dry
        settings.X_OAUTH_CLIENT_ID = prev_client
        settings.X_OAUTH_CALLBACK_URL = prev_callback
        await close_db()

    asyncio.run(_run())
