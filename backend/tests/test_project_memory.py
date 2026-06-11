import asyncio

import pytest

from app.config import settings
from app.memory.db import close_db, init_db
from app.memory.project_memory import ProjectMemoryService, new_project_id


async def _reset_memory_db(database_url: str) -> None:
    settings.DATABASE_URL = database_url
    await close_db()
    await init_db()


async def _test_append_version_and_finalize_project() -> None:
    await _reset_memory_db("sqlite+aiosqlite:///:memory:")
    service = ProjectMemoryService()
    project_id = new_project_id()

    v1 = await service.append_version(
        project_id=project_id,
        parent_version_id=None,
        intent="new_task",
        user_input="写一篇东京攻略",
        result={"title": "东京自由行", "content": "正文", "hashtags": []},
        planning={"topic": "东京自由行", "tone_style": "活泼"},
    )
    assert v1.version_label == "v1"
    assert v1.version_number == 1

    v2 = await service.append_version(
        project_id=project_id,
        parent_version_id=v1.version_id,
        intent="refine_content",
        user_input="语气更活泼",
        result={"title": "东京自由行攻略", "content": "更活泼正文", "hashtags": []},
        planning={"topic": "东京自由行", "tone_style": "更活泼"},
    )
    assert v2.version_label == "v2"
    assert v2.parent_version_id == v1.version_id

    project = await service.get_project(project_id)
    assert project is None

    row = await service.finalize_project(project_id)
    assert row is not None
    assert row.project_id == project_id
    assert row.final_version == "v2"
    assert row.topic == "东京自由行"
    assert "东京自由行" in row.project_summary

    await close_db()


async def _test_finalize_without_versions_returns_none() -> None:
    await _reset_memory_db("sqlite+aiosqlite:///:memory:")
    service = ProjectMemoryService()
    project_id = new_project_id()
    row = await service.finalize_project(project_id)
    assert row is None
    await close_db()


def test_append_version_and_finalize_project() -> None:
    asyncio.run(_test_append_version_and_finalize_project())


def test_finalize_without_versions_returns_none() -> None:
    asyncio.run(_test_finalize_without_versions_returns_none())


async def _test_list_projects_sorted_by_last_accessed_at() -> None:
    await _reset_memory_db("sqlite+aiosqlite:///:memory:")
    service = ProjectMemoryService()
    older = await service.create_project()
    newer = await service.create_project()

    await service.append_version(
        project_id=older,
        parent_version_id=None,
        intent="new_task",
        user_input="旧项目新内容",
        result={"title": "旧项目", "content": "正文", "hashtags": []},
        planning=None,
    )
    await service.touch_project(older)

    rows = await service.list_projects()
    assert [row.project_id for row in rows] == [older, newer]

    await close_db()


def test_list_projects_sorted_by_last_accessed_at() -> None:
    asyncio.run(_test_list_projects_sorted_by_last_accessed_at())
