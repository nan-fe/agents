import asyncio
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app
from app.memory.db import close_db, get_session, init_db
from app.memory.models import ProjectRow
from app.memory.project_memory import ProjectMemoryService


@pytest.fixture(autouse=True)
def memory_db(monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_URL", "sqlite+aiosqlite:///:memory:")


async def _run_project_api_flow() -> None:
    await close_db()
    await init_db()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        list_empty = await client.get("/projects")
        assert list_empty.status_code == 200
        assert list_empty.json()["projects"] == []

        create_resp = await client.post("/projects", json={})
        assert create_resp.status_code == 200
        project_id = create_resp.json()["project_id"]
        assert project_id.startswith("proj_")

        list_after_create = await client.get("/projects")
        assert list_after_create.status_code == 200
        assert list_after_create.json()["projects"] == []

        service = ProjectMemoryService()
        assert await service.get_project(project_id) is None

        empty = await client.get(f"/projects/{project_id}")
        assert empty.status_code == 200
        assert empty.json()["versions"] == []

        await service.append_version(
            project_id=project_id,
            parent_version_id=None,
            intent="new_task",
            user_input="写一篇防晒文案",
            result={
                "title": "防晒推荐",
                "content": "正文",
                "hashtags": ["#防晒"],
                "image_url": "",
            },
            planning={"topic": "防晒"},
        )

        loaded = await client.get(f"/projects/{project_id}")
        assert loaded.status_code == 200
        body = loaded.json()
        assert len(body["versions"]) == 1
        assert body["versions"][0]["user_input"] == "写一篇防晒文案"
        assert body["final_version"] == "v1"

    await close_db()


def test_project_create_and_conversation_api() -> None:
    asyncio.run(_run_project_api_flow())


async def _test_list_projects_filters_empty_metadata() -> None:
    await close_db()
    await init_db()
    now = datetime.now(timezone.utc)
    empty_id = "proj_empty000001"
    valid_id = "proj_valid000001"
    async with get_session() as session:
        session.add(
            ProjectRow(
                project_id=empty_id,
                topic="",
                final_version=None,
                project_summary="",
                created_at=now,
                updated_at=now,
                last_accessed_at=now,
            )
        )
        session.add(
            ProjectRow(
                project_id=valid_id,
                topic="有效项目",
                final_version="v1",
                project_summary="摘要",
                created_at=now,
                updated_at=now,
                last_accessed_at=now,
            )
        )
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/projects")
        assert response.status_code == 200
        project_ids = [item["project_id"] for item in response.json()["projects"]]
        assert empty_id not in project_ids
        assert valid_id in project_ids

    await close_db()


def test_list_projects_filters_empty_metadata() -> None:
    asyncio.run(_test_list_projects_filters_empty_metadata())
