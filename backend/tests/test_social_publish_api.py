"""社交媒体发布 API 测试。"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app
from app.memory.db import close_db, init_db
from app.services.social.publish_job_store import publish_job_store


@pytest.fixture(autouse=True)
def memory_db(monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_URL", "sqlite+aiosqlite:///:memory:")


async def _run_social_api_flow() -> None:
    await close_db()
    await init_db()

    monkeypatch_enabled = settings.WEIBO_PUBLISH_ENABLED
    monkeypatch_dry = settings.WEIBO_PUBLISH_DRY_RUN
    settings.WEIBO_PUBLISH_ENABLED = True
    settings.WEIBO_PUBLISH_DRY_RUN = True
    settings.WEIBO_PUBLISH_SKIP_REVIEW = False

    mock_publish = AsyncMock(return_value=("https://weibo.com/dry-run", None))

    transport = ASGITransport(app=app)
    with patch(
        "app.services.social.weibo_publisher.publish_to_weibo",
        mock_publish,
    ):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            status_resp = await client.get("/social/status")
            assert status_resp.status_code == 200
            body = status_resp.json()
            assert body["weibo_publish_enabled"] is True
            assert "review_required" in body

            blocked = await client.post(
                "/social/publish/weibo",
                json={"title": "标题", "content": "正文", "review_approved": False},
            )
            assert blocked.status_code == 400

            create_resp = await client.post(
                "/social/publish/weibo",
                json={
                    "title": "标题",
                    "content": "正文",
                    "hashtags": ["测试"],
                    "review_approved": True,
                    "share_url": "https://example.com/share/x",
                },
            )
            assert create_resp.status_code == 200
            job_id = create_resp.json()["job_id"]
            assert job_id

            for _ in range(20):
                job_resp = await client.get(f"/social/publish/{job_id}")
                assert job_resp.status_code == 200
                job = job_resp.json()
                if job["status"] in {"succeeded", "failed"}:
                    break
                await asyncio.sleep(0.05)
            else:
                pytest.fail("发布任务未在预期时间内完成")

            assert job["status"] == "succeeded"
            assert job["post_url"] == "https://weibo.com/dry-run"

            sync_resp = await client.post("/social/sync/x")
            assert sync_resp.status_code == 200

    settings.WEIBO_PUBLISH_ENABLED = monkeypatch_enabled
    settings.WEIBO_PUBLISH_DRY_RUN = monkeypatch_dry
    await close_db()


def test_social_publish_api() -> None:
    asyncio.run(_run_social_api_flow())


def test_social_publish_missing_content() -> None:
    async def _run() -> None:
        await close_db()
        await init_db()
        settings.WEIBO_PUBLISH_ENABLED = True
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/social/publish/weibo", json={})
            assert resp.status_code == 400
        await close_db()

    asyncio.run(_run())


def test_publish_job_store_lifecycle() -> None:
    async def _run() -> None:
        job = await publish_job_store.create_job(platform="weibo", payload_summary={"t": "x"})
        await publish_job_store.append_progress(job.job_id, "step1")
        await publish_job_store.mark_running(job.job_id)
        await publish_job_store.mark_succeeded(job.job_id, post_url="https://weibo.com/1")
        loaded = await publish_job_store.get_job(job.job_id)
        assert loaded is not None
        assert loaded.status.value == "succeeded"
        assert loaded.progress == ["step1"]

    asyncio.run(_run())
