"""微博可视化登录 API 测试。"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app
from app.memory.db import close_db, init_db
from app.services.social.weibo_login_session import WeiboLoginSession


@pytest.fixture(autouse=True)
def memory_db(monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_URL", "sqlite+aiosqlite:///:memory:")


def _mock_session(*, logged_in: bool = False) -> WeiboLoginSession:
    session = WeiboLoginSession(
        session_id="test-session",
        browser_session=MagicMock(),
    )
    session.screenshot_png = AsyncMock(return_value=b"png-bytes")  # type: ignore[method-assign]
    session.click = AsyncMock()  # type: ignore[method-assign]
    session.type_text = AsyncMock()  # type: ignore[method-assign]
    session.press_key = AsyncMock()  # type: ignore[method-assign]
    session.evaluate_login = AsyncMock(  # type: ignore[method-assign]
        return_value={
            "logged_in": logged_in,
            "current_url": "https://weibo.com/"
            if logged_in
            else "https://passport.weibo.com/login",
            "profile_path": "/tmp/weibo-profile",
        },
    )
    session.close = AsyncMock()  # type: ignore[method-assign]
    return session


def test_weibo_login_api_flow() -> None:
    async def _run() -> None:
        await close_db()
        await init_db()

        prev_enabled = settings.WEIBO_PUBLISH_ENABLED
        prev_dry = settings.WEIBO_PUBLISH_DRY_RUN
        settings.WEIBO_PUBLISH_ENABLED = True
        settings.WEIBO_PUBLISH_DRY_RUN = False

        session = _mock_session(logged_in=False)

        transport = ASGITransport(app=app)
        with patch(
            "app.main.weibo_login_session_manager.start",
            AsyncMock(return_value=session),
        ):
            with patch(
                "app.main.weibo_login_session_manager.get",
                AsyncMock(return_value=session),
            ):
                with patch(
                    "app.main.weibo_login_session_manager.close",
                    AsyncMock(),
                ):
                    async with AsyncClient(transport=transport, base_url="http://test") as client:
                        start_resp = await client.post("/social/weibo/login/start")
                        assert start_resp.status_code == 200
                        body = start_resp.json()
                        assert body["session_id"] == "test-session"
                        assert body["logged_in"] is False

                        shot_resp = await client.get(
                            "/social/weibo/login/test-session/screenshot",
                        )
                        assert shot_resp.status_code == 200
                        assert shot_resp.content == b"png-bytes"

                        click_resp = await client.post(
                            "/social/weibo/login/test-session/click",
                            json={"x": 100, "y": 200},
                        )
                        assert click_resp.status_code == 200
                        assert click_resp.json()["ok"] is True

                        close_resp = await client.delete(
                            "/social/weibo/login/test-session",
                        )
                        assert close_resp.status_code == 200

        settings.WEIBO_PUBLISH_ENABLED = prev_enabled
        settings.WEIBO_PUBLISH_DRY_RUN = prev_dry
        await close_db()

    asyncio.run(_run())


def test_weibo_login_start_disabled() -> None:
    async def _run() -> None:
        await close_db()
        await init_db()
        prev = settings.WEIBO_PUBLISH_ENABLED
        settings.WEIBO_PUBLISH_ENABLED = False
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/social/weibo/login/start")
            assert resp.status_code == 400
        settings.WEIBO_PUBLISH_ENABLED = prev
        await close_db()

    asyncio.run(_run())
