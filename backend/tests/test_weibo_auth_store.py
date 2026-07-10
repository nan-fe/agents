"""微博登录态数据库持久化测试。"""

from __future__ import annotations

import asyncio

import pytest

from app.config import settings
from app.memory.db import close_db, init_db
from app.services.social.weibo_auth_store import get_weibo_auth, save_weibo_auth


@pytest.fixture(autouse=True)
def memory_db(monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_URL", "sqlite+aiosqlite:///:memory:")


def test_save_and_get_weibo_auth() -> None:
    async def _run() -> None:
        await close_db()
        await init_db()

        assert await get_weibo_auth() is None

        await save_weibo_auth(
            profile_path="/tmp/weibo-profile",
            logged_in=True,
            current_url="https://weibo.com/",
        )
        stored = await get_weibo_auth()
        assert stored is not None
        assert stored["logged_in"] is True
        assert stored["profile_path"] == "/tmp/weibo-profile"
        assert stored["current_url"] == "https://weibo.com/"
        assert stored["confirmed_at"] is not None

        await close_db()

    asyncio.run(_run())
