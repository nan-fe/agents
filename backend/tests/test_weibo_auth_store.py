"""微博登录态持久化单元测试。"""

from __future__ import annotations

import asyncio

import pytest

from app.config import settings
from app.memory.db import close_db, init_db
from app.services.social.weibo_auth_store import clear_weibo_auth, get_weibo_auth, save_weibo_auth


@pytest.fixture(autouse=True)
def memory_db(monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_URL", "sqlite+aiosqlite:///:memory:")


def test_save_and_get_weibo_auth() -> None:
    async def _run() -> None:
        await close_db()
        await init_db()

        assert await get_weibo_auth("demo") is None

        await save_weibo_auth(
            user_id="demo",
            profile_path="/tmp/weibo-profile",
            logged_in=True,
            current_url="https://weibo.com/",
        )
        stored = await get_weibo_auth("demo")
        assert stored is not None
        assert stored["logged_in"] is True
        assert stored["profile_path"] == "/tmp/weibo-profile"

        await clear_weibo_auth("demo")
        stored_after = await get_weibo_auth("demo")
        assert stored_after is not None
        assert stored_after["logged_in"] is False

        await close_db()

    asyncio.run(_run())
