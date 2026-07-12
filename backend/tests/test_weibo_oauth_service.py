"""微博 OAuth 服务单元测试。"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from app.config import settings
from app.memory.db import close_db, get_session, init_db
from app.memory.models import WeiboUserTokenRow
from app.services.social.weibo_oauth_service import weibo_oauth_service


@pytest.fixture(autouse=True)
def memory_db(monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_URL", "sqlite+aiosqlite:///:memory:")


def test_user_status_manual_profile_without_oauth() -> None:
    async def _run() -> None:
        await close_db()
        await init_db()
        prev_client = settings.WEIBO_OAUTH_CLIENT_ID
        settings.WEIBO_OAUTH_CLIENT_ID = ""

        status = await weibo_oauth_service.user_status("demo", profile_logged_in=True)
        assert status["connected"] is True
        assert status["oauth_connected"] is False
        assert status["profile_ready"] is True

        settings.WEIBO_OAUTH_CLIENT_ID = prev_client
        await close_db()

    asyncio.run(_run())


def test_user_status_requires_both_when_oauth_configured() -> None:
    async def _run() -> None:
        await close_db()
        await init_db()
        prev_enabled = settings.WEIBO_PUBLISH_ENABLED
        prev_client = settings.WEIBO_OAUTH_CLIENT_ID
        prev_secret = settings.WEIBO_OAUTH_CLIENT_SECRET
        prev_callback = settings.WEIBO_OAUTH_CALLBACK_URL
        settings.WEIBO_PUBLISH_ENABLED = True
        settings.WEIBO_OAUTH_CLIENT_ID = "test-client"
        settings.WEIBO_OAUTH_CLIENT_SECRET = "test-secret"
        settings.WEIBO_OAUTH_CALLBACK_URL = "http://localhost:8000/social/weibo/oauth/callback"

        now = datetime.now(UTC)
        async with get_session() as session:
            session.add(
                WeiboUserTokenRow(
                    user_id="demo",
                    access_token="token",
                    expires_at=now + timedelta(hours=2),
                    weibo_screen_name="demo_user",
                    updated_at=now,
                )
            )
            await session.commit()

        only_token = await weibo_oauth_service.user_status("demo", profile_logged_in=False)
        assert only_token["oauth_connected"] is True
        assert only_token["connected"] is False

        ready = await weibo_oauth_service.user_status("demo", profile_logged_in=True)
        assert ready["connected"] is True

        settings.WEIBO_PUBLISH_ENABLED = prev_enabled
        settings.WEIBO_OAUTH_CLIENT_ID = prev_client
        settings.WEIBO_OAUTH_CLIENT_SECRET = prev_secret
        settings.WEIBO_OAUTH_CALLBACK_URL = prev_callback
        await close_db()

    asyncio.run(_run())
