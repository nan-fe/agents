import asyncio

from app.config import settings
from app.memory.db import close_db, init_db
from app.memory.project_memory import ProjectMemoryService, new_project_id

TEST_USER_ID = "user_test001"


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
        user_id=TEST_USER_ID,
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
        user_id=TEST_USER_ID,
    )
    assert v2.version_label == "v2"
    assert v2.parent_version_id == v1.version_id

    project = await service.get_project(project_id)
    assert project is None

    row = await service.finalize_project(project_id, user_id=TEST_USER_ID)
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
    row = await service.finalize_project(project_id, user_id=TEST_USER_ID)
    assert row is None
    await close_db()


def test_append_version_and_finalize_project() -> None:
    asyncio.run(_test_append_version_and_finalize_project())


def test_finalize_without_versions_returns_none() -> None:
    asyncio.run(_test_finalize_without_versions_returns_none())


async def _test_list_projects_sorted_by_last_accessed_at() -> None:
    await _reset_memory_db("sqlite+aiosqlite:///:memory:")
    service = ProjectMemoryService()
    older = new_project_id()
    newer = new_project_id()

    await service.append_version(
        project_id=older,
        parent_version_id=None,
        intent="new_task",
        user_input="旧项目新内容",
        result={"title": "旧项目", "content": "正文", "hashtags": []},
        planning=None,
        user_id=TEST_USER_ID,
    )
    await service.finalize_project(older, user_id=TEST_USER_ID)
    await service.ensure_project_stub(
        newer,
        user_id=TEST_USER_ID,
        topic="新项目",
        final_version="v0",
    )
    await service.touch_project(older, user_id=TEST_USER_ID)

    rows = await service.list_projects(user_id=TEST_USER_ID)
    assert [row.project_id for row in rows] == [older, newer]

    await close_db()


def test_list_projects_sorted_by_last_accessed_at() -> None:
    asyncio.run(_test_list_projects_sorted_by_last_accessed_at())


async def _test_version_counts_batch() -> None:
    await _reset_memory_db("sqlite+aiosqlite:///:memory:")
    service = ProjectMemoryService()
    project_a = await service.create_project()
    project_b = await service.create_project()

    await service.append_version(
        project_id=project_a,
        parent_version_id=None,
        intent="new_task",
        user_input="A1",
        result={"title": "A", "content": "正文", "hashtags": []},
        planning=None,
        user_id=TEST_USER_ID,
    )
    await service.append_version(
        project_id=project_a,
        parent_version_id=None,
        intent="refine_content",
        user_input="A2",
        result={"title": "A2", "content": "正文", "hashtags": []},
        planning=None,
        user_id=TEST_USER_ID,
    )

    counts = await service.version_counts(
        [project_a, project_b, "missing"],
        user_id=TEST_USER_ID,
    )
    assert counts == {project_a: 2, project_b: 0, "missing": 0}

    await close_db()


def test_version_counts_batch() -> None:
    asyncio.run(_test_version_counts_batch())


async def _test_ensure_project_stub_is_idempotent() -> None:
    await _reset_memory_db("sqlite+aiosqlite:///:memory:")
    service = ProjectMemoryService()
    project_id = new_project_id()

    assert await service.get_project(project_id) is None

    await service.ensure_project_stub(
        project_id,
        user_id="user-1",
        topic="测试主题",
        final_version="v1",
    )
    first = await service.get_project(project_id)
    assert first is not None
    assert first.user_id == "user-1"

    await service.ensure_project_stub(
        project_id,
        user_id="user-2",
        topic="测试主题",
        final_version="v1",
    )
    second = await service.get_project(project_id)
    assert second is not None
    assert second.user_id == "user-1"

    await close_db()


def test_ensure_project_stub_is_idempotent() -> None:
    asyncio.run(_test_ensure_project_stub_is_idempotent())


async def _test_ensure_project_stub_skips_without_topic_or_version() -> None:
    await _reset_memory_db("sqlite+aiosqlite:///:memory:")
    service = ProjectMemoryService()
    project_id = new_project_id()

    await service.ensure_project_stub(project_id, topic="仅有主题")
    await service.ensure_project_stub(project_id, final_version="v1")
    assert await service.get_project(project_id) is None

    await close_db()


def test_ensure_project_stub_skips_without_topic_or_version() -> None:
    asyncio.run(_test_ensure_project_stub_skips_without_topic_or_version())


async def _test_create_project_does_not_write_row() -> None:
    await _reset_memory_db("sqlite+aiosqlite:///:memory:")
    service = ProjectMemoryService()
    project_id = await service.create_project()
    assert project_id.startswith("proj_")
    assert await service.get_project(project_id) is None
    await close_db()


def test_create_project_does_not_write_row() -> None:
    asyncio.run(_test_create_project_does_not_write_row())


async def _test_touch_project_materializes_version_only_project() -> None:
    await _reset_memory_db("sqlite+aiosqlite:///:memory:")
    service = ProjectMemoryService()
    stale = new_project_id()
    active = new_project_id()

    await service.ensure_project_stub(
        stale,
        user_id=TEST_USER_ID,
        topic="较早打开",
        final_version="v0",
    )
    await service.append_version(
        project_id=active,
        parent_version_id=None,
        intent="new_task",
        user_input="仅有版本",
        result={"title": "版本项目", "content": "正文", "hashtags": []},
        planning={"topic": "版本项目"},
        user_id=TEST_USER_ID,
    )
    await service.touch_project(active, user_id=TEST_USER_ID)

    rows = await service.list_projects(user_id=TEST_USER_ID)
    assert [row.project_id for row in rows] == [active, stale]
    assert await service.get_project(active) is not None

    await close_db()


def test_touch_project_materializes_version_only_project() -> None:
    asyncio.run(_test_touch_project_materializes_version_only_project())


async def _test_finalize_existing_row_does_not_bump_last_accessed_at() -> None:
    await _reset_memory_db("sqlite+aiosqlite:///:memory:")
    service = ProjectMemoryService()
    project_id = new_project_id()

    v1 = await service.append_version(
        project_id=project_id,
        parent_version_id=None,
        intent="new_task",
        user_input="初稿",
        result={"title": "主题", "content": "正文", "hashtags": []},
        planning={"topic": "主题"},
        user_id=TEST_USER_ID,
    )
    row = await service.finalize_project(project_id, user_id=TEST_USER_ID)
    assert row is not None
    first_accessed = row.last_accessed_at

    await asyncio.sleep(0.02)
    await service.append_version(
        project_id=project_id,
        parent_version_id=v1.version_id,
        intent="refine_content",
        user_input="修订",
        result={"title": "主题修订", "content": "新正文", "hashtags": []},
        planning={"topic": "主题"},
        user_id=TEST_USER_ID,
    )
    row = await service.finalize_project(project_id, user_id=TEST_USER_ID)
    assert row is not None
    assert row.last_accessed_at == first_accessed

    await close_db()


def test_finalize_existing_row_does_not_bump_last_accessed_at() -> None:
    asyncio.run(_test_finalize_existing_row_does_not_bump_last_accessed_at())


async def _test_delete_project_removes_rows_and_versions() -> None:
    await _reset_memory_db("sqlite+aiosqlite:///:memory:")
    service = ProjectMemoryService()
    keep_id = new_project_id()
    delete_id = new_project_id()

    v1 = await service.append_version(
        project_id=delete_id,
        parent_version_id=None,
        intent="new_task",
        user_input="待删除",
        result={"title": "删除项", "content": "正文", "hashtags": []},
        planning={"topic": "删除项"},
        user_id=TEST_USER_ID,
    )
    await service.append_version(
        project_id=delete_id,
        parent_version_id=v1.version_id,
        intent="refine_content",
        user_input="修订",
        result={"title": "删除项修订", "content": "新正文", "hashtags": []},
        planning={"topic": "删除项"},
        user_id=TEST_USER_ID,
    )
    await service.finalize_project(delete_id, user_id=TEST_USER_ID)

    await service.append_version(
        project_id=keep_id,
        parent_version_id=None,
        intent="new_task",
        user_input="保留",
        result={"title": "保留项", "content": "正文", "hashtags": []},
        planning={"topic": "保留项"},
        user_id=TEST_USER_ID,
    )
    await service.finalize_project(keep_id, user_id=TEST_USER_ID)

    assert await service.delete_project(delete_id, user_id=TEST_USER_ID) is True
    assert await service.delete_project(delete_id, user_id=TEST_USER_ID) is False
    assert await service.delete_project("", user_id=TEST_USER_ID) is False

    assert await service.get_project(delete_id) is None
    assert await service.list_versions(delete_id, user_id=TEST_USER_ID) == []
    assert await service.get_project(keep_id) is not None
    assert len(await service.list_versions(keep_id, user_id=TEST_USER_ID)) == 1

    rows = await service.list_projects(user_id=TEST_USER_ID)
    assert delete_id not in {row.project_id for row in rows}
    assert keep_id in {row.project_id for row in rows}

    await close_db()


def test_delete_project_removes_rows_and_versions() -> None:
    asyncio.run(_test_delete_project_removes_rows_and_versions())


async def _test_project_user_isolation() -> None:
    await _reset_memory_db("sqlite+aiosqlite:///:memory:")
    service = ProjectMemoryService()
    project_id = new_project_id()

    await service.append_version(
        project_id=project_id,
        parent_version_id=None,
        intent="new_task",
        user_input="用户 A 的内容",
        result={"title": "A 项目", "content": "正文", "hashtags": []},
        planning={"topic": "A 项目"},
        user_id="user_a",
    )
    await service.finalize_project(project_id, user_id="user_a")

    assert await service.project_accessible(project_id, "user_a") is True
    assert await service.project_accessible(project_id, "user_b") is False
    assert await service.list_versions(project_id, user_id="user_b") == []
    assert await service.delete_project(project_id, user_id="user_b") is False
    assert await service.delete_project(project_id, user_id="user_a") is True

    await close_db()


def test_project_user_isolation() -> None:
    asyncio.run(_test_project_user_isolation())
