import asyncio
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app
from app.memory.db import close_db, get_session, init_db
from app.memory.models import ProjectRow
from app.memory.project_memory import ProjectMemoryService, new_project_id

TEST_USER_ID = "user_test001"
OTHER_USER_ID = "user_other001"


@pytest.fixture(autouse=True)
def memory_db(monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_URL", "sqlite+aiosqlite:///:memory:")


async def _run_project_api_flow() -> None:
    await close_db()
    await init_db()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        list_missing_user = await client.get("/projects")
        assert list_missing_user.status_code == 400

        list_empty = await client.get("/projects", params={"user_id": TEST_USER_ID})
        assert list_empty.status_code == 200
        assert list_empty.json()["projects"] == []

        create_resp = await client.post(
            "/projects",
            json={"user_id": TEST_USER_ID},
        )
        assert create_resp.status_code == 200
        project_id = create_resp.json()["project_id"]
        assert project_id.startswith("proj_")

        list_after_create = await client.get("/projects", params={"user_id": TEST_USER_ID})
        assert list_after_create.status_code == 200
        assert list_after_create.json()["projects"] == []

        service = ProjectMemoryService()
        assert await service.get_project(project_id) is None

        empty = await client.get(
            f"/projects/{project_id}",
            params={"user_id": TEST_USER_ID},
        )
        assert empty.status_code == 404

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
            user_id=TEST_USER_ID,
        )

        loaded = await client.get(
            f"/projects/{project_id}",
            params={"user_id": TEST_USER_ID},
        )
        assert loaded.status_code == 200
        body = loaded.json()
        assert len(body["versions"]) == 1
        assert body["versions"][0]["user_input"] == "写一篇防晒文案"
        assert body["final_version"] == "v1"

        other_user = await client.get(
            f"/projects/{project_id}",
            params={"user_id": OTHER_USER_ID},
        )
        assert other_user.status_code == 404

    await close_db()


def test_project_create_and_conversation_api() -> None:
    asyncio.run(_run_project_api_flow())


async def _test_list_projects_filters_empty_metadata() -> None:
    await close_db()
    await init_db()
    now = datetime.now(UTC)
    empty_id = "proj_empty000001"
    valid_id = "proj_valid000001"
    async with get_session() as session:
        session.add(
            ProjectRow(
                project_id=empty_id,
                user_id=TEST_USER_ID,
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
                user_id=TEST_USER_ID,
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
        response = await client.get("/projects", params={"user_id": TEST_USER_ID})
        assert response.status_code == 200
        project_ids = [item["project_id"] for item in response.json()["projects"]]
        assert empty_id not in project_ids
        assert valid_id in project_ids

    await close_db()


def test_list_projects_filters_empty_metadata() -> None:
    asyncio.run(_test_list_projects_filters_empty_metadata())


async def _test_delete_project_api() -> None:
    await close_db()
    await init_db()

    service = ProjectMemoryService()
    project_id = new_project_id()

    v1 = await service.append_version(
        project_id=project_id,
        parent_version_id=None,
        intent="new_task",
        user_input="写一篇防晒文案",
        result={"title": "防晒推荐", "content": "正文", "hashtags": []},
        planning={"topic": "防晒"},
        user_id=TEST_USER_ID,
    )
    await service.append_version(
        project_id=project_id,
        parent_version_id=v1.version_id,
        intent="refine_content",
        user_input="语气更活泼",
        result={"title": "防晒推荐修订", "content": "新正文", "hashtags": []},
        planning={"topic": "防晒"},
        user_id=TEST_USER_ID,
    )
    await service.finalize_project(project_id, user_id=TEST_USER_ID)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        list_before = await client.get("/projects", params={"user_id": TEST_USER_ID})
        assert project_id in [item["project_id"] for item in list_before.json()["projects"]]

        missing = await client.delete(
            "/projects/proj_not_exists",
            params={"user_id": TEST_USER_ID},
        )
        assert missing.status_code == 404

        forbidden = await client.delete(
            f"/projects/{project_id}",
            params={"user_id": OTHER_USER_ID},
        )
        assert forbidden.status_code == 404

        deleted = await client.delete(
            f"/projects/{project_id}",
            params={"user_id": TEST_USER_ID},
        )
        assert deleted.status_code == 200
        assert deleted.json()["ok"] is True

        list_after = await client.get("/projects", params={"user_id": TEST_USER_ID})
        assert project_id not in [item["project_id"] for item in list_after.json()["projects"]]

        loaded = await client.get(
            f"/projects/{project_id}",
            params={"user_id": TEST_USER_ID},
        )
        assert loaded.status_code == 404

    assert await service.get_project(project_id) is None
    assert await service.list_versions(project_id, user_id=TEST_USER_ID) == []

    await close_db()


def test_delete_project_api() -> None:
    asyncio.run(_test_delete_project_api())


async def _test_finalize_empty_client_project_id() -> None:
    """POST /projects 仅分配 ID，未写入 versions 时 finalize 应跳过而非 404。"""
    await close_db()
    await init_db()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create_resp = await client.post("/projects", json={"user_id": TEST_USER_ID})
        project_id = create_resp.json()["project_id"]

        finalize_resp = await client.post(
            "/projects/finalize",
            json={
                "project_id": project_id,
                "session_id": "session_test",
                "user_id": TEST_USER_ID,
            },
        )
        assert finalize_resp.status_code == 200
        body = finalize_resp.json()
        assert body["finalized"] is False
        assert body["version_count"] == 0

    await close_db()


def test_finalize_empty_client_project_id() -> None:
    asyncio.run(_test_finalize_empty_client_project_id())
