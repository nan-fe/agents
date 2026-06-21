"""飞书推送 API 测试。"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app
from app.memory.db import close_db, init_db
from app.memory.project_memory import ProjectMemoryService
from lark_im.settings import lark_settings


@pytest.fixture(autouse=True)
def memory_db(monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_URL", "sqlite+aiosqlite:///:memory:")


async def _run_lark_api_flow() -> None:
    await close_db()
    await init_db()

    mock_service = AsyncMock()
    mock_service.get_auth_status = AsyncMock(
        return_value={"bot": {"available": True}, "user": {"available": False}}
    )
    mock_service.send_review_notification = AsyncMock(
        return_value={"message_id": "om_test"}
    )

    transport = ASGITransport(app=app)
    with patch("app.main.get_lark_im_service", return_value=mock_service):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            status_resp = await client.get("/lark/status")
            assert status_resp.status_code == 200
            body = status_resp.json()
            assert body["auth"]["bot"]["available"] is True
            assert "notify_mode" in body

            push_resp = await client.post(
                "/lark/push-review",
                json={
                    "title": "测试标题",
                    "content": "测试正文",
                    "project_id": "proj_test",
                },
            )
            assert push_resp.status_code == 200
            assert push_resp.json()["ok"] is True
            mock_service.send_review_notification.assert_awaited_once()

            service = ProjectMemoryService()
            version_row = await service.append_version(
                project_id="proj_push",
                parent_version_id=None,
                intent="new_task",
                user_input="写文案",
                result={
                    "title": "版本标题",
                    "content": "版本正文",
                    "hashtags": ["#测试"],
                    "image_url": "",
                    "review_approved": True,
                },
                planning={},
            )

            by_version = await client.post(
                "/lark/push-review",
                json={"version_id": version_row.version_id},
            )
            assert by_version.status_code == 200
            assert mock_service.send_review_notification.await_count == 2

    await close_db()


def test_lark_status_and_push_review_api() -> None:
    asyncio.run(_run_lark_api_flow())


def test_lark_push_review_missing_content() -> None:
    async def _run():
        await close_db()
        await init_db()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/lark/push-review", json={})
            assert resp.status_code == 400
        await close_db()

    asyncio.run(_run())


def test_is_lark_notify_configured(monkeypatch) -> None:
    monkeypatch.setattr(lark_settings, "LARK_APP_ID", "cli_test")
    monkeypatch.setattr(lark_settings, "LARK_APP_SECRET", "secret")
    monkeypatch.setattr(lark_settings, "LARK_NOTIFY_CHAT_ID", "oc_test")
    from lark_im.notify import is_lark_notify_configured

    assert is_lark_notify_configured() is True

    monkeypatch.setattr(lark_settings, "LARK_NOTIFY_CHAT_ID", "")
    assert is_lark_notify_configured() is False
