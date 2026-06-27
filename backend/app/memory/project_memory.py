"""Project Memory：versions 即时写入，projects 在 finalize 时汇总。"""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func, select, update

from app.memory.db import get_session
from app.memory.models import ProjectRow, VersionRow


def new_project_id() -> str:
    return f"proj_{uuid.uuid4().hex[:12]}"


def _utcnow() -> datetime:
    return datetime.now(UTC)


def normalize_user_id(user_id: str | None) -> str | None:
    uid = (user_id or "").strip()
    return uid or None


def build_version_summary(intent: str, user_input: str, result: dict[str, Any]) -> str:
    title = (result.get("title") or "").strip()
    if title:
        return title[:120]
    snippet = (user_input or "").strip()[:60]
    return f"{intent or 'create'}: {snippet}" if snippet else intent or "version"


def should_persist_project_row(topic: str | None, final_version: str | None) -> bool:
    return bool((topic or "").strip()) and bool((final_version or "").strip())


def metadata_from_version(version: VersionRow) -> tuple[str, str]:
    planning = version.planning or {}
    topic = (planning.get("topic") or "").strip() or ((version.result.get("title") or "").strip())
    return topic, version.version_label


class ProjectMemoryService:
    async def project_has_versions(self, project_id: str) -> bool:
        project_id = (project_id or "").strip()
        if not project_id:
            return False

        async with get_session() as session:
            result = await session.execute(
                select(func.count())
                .select_from(VersionRow)
                .where(VersionRow.project_id == project_id)
            )
            return int(result.scalar_one()) > 0

    async def project_accessible(self, project_id: str, user_id: str | None) -> bool:
        uid = normalize_user_id(user_id)
        project_id = (project_id or "").strip()
        if not uid or not project_id:
            return False

        project = await self.get_project(project_id)
        if project is not None:
            return project.user_id == uid

        async with get_session() as session:
            result = await session.execute(
                select(VersionRow.user_id)
                .where(VersionRow.project_id == project_id)
                .distinct()
            )
            user_ids = [row[0] for row in result.all()]

        if not user_ids:
            return False
        return user_ids == [uid]

    async def ensure_project_stub(
        self,
        project_id: str,
        *,
        user_id: str | None = None,
        topic: str | None = None,
        final_version: str | None = None,
    ) -> None:
        """若 projects 表尚无该行且具备 topic/final_version，写入 stub（幂等）。"""
        project_id = (project_id or "").strip()
        topic = (topic or "").strip()
        final_version = (final_version or "").strip()
        uid = normalize_user_id(user_id)
        if not project_id or not should_persist_project_row(topic, final_version):
            return

        async with get_session() as session:
            existing = await session.get(ProjectRow, project_id)
            if existing is not None:
                if uid and existing.user_id is None:
                    existing.user_id = uid
                    await session.commit()
                return

            now = _utcnow()
            session.add(
                ProjectRow(
                    project_id=project_id,
                    user_id=uid,
                    topic=topic,
                    final_version=final_version,
                    project_summary="",
                    created_at=now,
                    updated_at=now,
                    last_accessed_at=now,
                )
            )
            await session.commit()

    async def create_project(self, *, user_id: str | None = None) -> str:
        """分配 project_id；无 topic/final_version 时不写入 projects 表。"""
        return new_project_id()

    async def touch_project(self, project_id: str, *, user_id: str | None = None) -> None:
        """记录用户打开项目的时间，不影响 updated_at（内容变更时间）。"""
        project_id = (project_id or "").strip()
        uid = normalize_user_id(user_id)
        if not project_id or not uid:
            return
        if not await self.project_accessible(project_id, uid):
            return

        async with get_session() as session:
            row = await session.get(ProjectRow, project_id)
            if row is not None:
                row.last_accessed_at = _utcnow()
                await session.commit()
                return

        versions = await self.list_versions(project_id, user_id=uid)
        if not versions:
            return

        topic, final_version = metadata_from_version(versions[-1])
        if not should_persist_project_row(topic, final_version):
            return

        await self.ensure_project_stub(
            project_id,
            user_id=uid,
            topic=topic,
            final_version=final_version,
        )
        async with get_session() as session:
            row = await session.get(ProjectRow, project_id)
            if row is not None:
                row.last_accessed_at = _utcnow()
                await session.commit()

    async def list_projects(self, *, user_id: str | None = None) -> list[ProjectRow]:
        uid = normalize_user_id(user_id)
        if not uid:
            return []

        async with get_session() as session:
            query = (
                select(ProjectRow)
                .where(ProjectRow.user_id == uid)
                .order_by(
                    ProjectRow.last_accessed_at.desc(),
                    ProjectRow.created_at.desc(),
                )
            )
            finalized = list((await session.execute(query)).scalars().all())

        finalized_ids = {row.project_id for row in finalized}
        orphan_items = await self._list_orphan_version_projects(
            exclude_ids=finalized_ids,
            user_id=uid,
        )
        return self._merge_project_lists(finalized, orphan_items)

    async def _list_orphan_version_projects(
        self,
        *,
        exclude_ids: set[str],
        user_id: str | None = None,
    ) -> list[ProjectRow]:
        """仅有 versions、尚未 finalize 的 project_id（兼容旧数据）。"""
        uid = normalize_user_id(user_id)
        if not uid:
            return []

        async with get_session() as session:
            rows = await session.execute(
                select(
                    VersionRow.project_id,
                    func.max(VersionRow.created_at),
                    func.count(),
                )
                .where(VersionRow.user_id == uid)
                .group_by(VersionRow.project_id)
                .order_by(func.max(VersionRow.created_at).desc())
            )

        orphans: list[ProjectRow] = []
        for project_id, latest_at, _count in rows.all():
            if project_id in exclude_ids:
                continue
            versions = await self.list_versions(project_id, user_id=uid)
            if not versions:
                continue
            latest = versions[-1]
            topic, final_version = metadata_from_version(latest)
            summaries = [v.summary for v in versions if v.summary]
            orphans.append(
                ProjectRow(
                    project_id=project_id,
                    user_id=uid,
                    topic=str(topic),
                    final_version=final_version,
                    project_summary=" → ".join(summaries[-8:]),
                    created_at=latest_at,
                    updated_at=latest_at,
                    last_accessed_at=latest_at,
                )
            )
        return orphans

    @staticmethod
    def _merge_project_lists(
        finalized: list[ProjectRow], orphans: list[ProjectRow]
    ) -> list[ProjectRow]:
        merged = list(finalized) + list(orphans)
        merged.sort(
            key=lambda row: (row.last_accessed_at, row.created_at),
            reverse=True,
        )
        return merged

    async def version_count(self, project_id: str, *, user_id: str | None = None) -> int:
        counts = await self.version_counts([project_id], user_id=user_id)
        return counts.get(project_id, 0)

    async def version_counts(
        self,
        project_ids: list[str],
        *,
        user_id: str | None = None,
    ) -> dict[str, int]:
        if not project_ids:
            return {}
        uid = normalize_user_id(user_id)
        async with get_session() as session:
            query = (
                select(VersionRow.project_id, func.count())
                .where(VersionRow.project_id.in_(project_ids))
                .group_by(VersionRow.project_id)
            )
            if uid:
                query = query.where(VersionRow.user_id == uid)
            rows = await session.execute(query)
        counts = dict.fromkeys(project_ids, 0)
        for project_id, count in rows.all():
            counts[str(project_id)] = int(count)
        return counts

    async def append_version(
        self,
        *,
        project_id: str,
        parent_version_id: str | None,
        intent: str,
        user_input: str,
        result: dict[str, Any],
        planning: dict[str, Any] | None,
        user_id: str | None = None,
    ) -> VersionRow:
        uid = normalize_user_id(user_id)
        async with get_session() as session:
            count_query = (
                select(func.count())
                .select_from(VersionRow)
                .where(VersionRow.project_id == project_id)
            )
            if uid:
                count_query = count_query.where(VersionRow.user_id == uid)
            count_result = await session.execute(count_query)
            version_number = int(count_result.scalar_one()) + 1
            version_label = f"v{version_number}"
            version_id = f"ver_{secrets.token_urlsafe(9)}"
            summary = build_version_summary(intent, user_input, result)

            row = VersionRow(
                version_id=version_id,
                project_id=project_id,
                user_id=uid,
                version_number=version_number,
                version_label=version_label,
                parent_version_id=parent_version_id,
                summary=summary,
                result=result,
                planning=planning,
                intent=intent,
                user_input=user_input,
            )
            session.add(row)
            project_row = await session.get(ProjectRow, project_id)
            if project_row is not None:
                project_row.updated_at = _utcnow()
                if uid and project_row.user_id is None:
                    project_row.user_id = uid
            await session.commit()
            await session.refresh(row)
            return row

    async def list_versions(
        self,
        project_id: str,
        *,
        user_id: str | None = None,
    ) -> list[VersionRow]:
        project_id = (project_id or "").strip()
        uid = normalize_user_id(user_id)
        if not project_id:
            return []
        if uid and not await self.project_accessible(project_id, uid):
            return []

        async with get_session() as session:
            query = (
                select(VersionRow)
                .where(VersionRow.project_id == project_id)
                .order_by(VersionRow.version_number.asc())
            )
            if uid:
                query = query.where(VersionRow.user_id == uid)
            result = await session.execute(query)
            return list(result.scalars().all())

    async def get_latest_version(
        self,
        project_id: str,
        *,
        user_id: str | None = None,
    ) -> VersionRow | None:
        versions = await self.list_versions(project_id, user_id=user_id)
        return versions[-1] if versions else None

    async def finalize_project(
        self,
        project_id: str,
        *,
        user_id: str | None = None,
    ) -> ProjectRow | None:
        """将 versions 汇总写入 projects 表；无版本时返回 None。"""
        uid = normalize_user_id(user_id)
        if uid and not await self.project_accessible(project_id, uid):
            return None

        versions = await self.list_versions(project_id, user_id=uid)
        if not versions:
            return None

        latest = versions[-1]
        topic, final_version = metadata_from_version(latest)

        summaries = [v.summary for v in versions if v.summary]
        project_summary = " → ".join(summaries[-8:])

        now = _utcnow()
        async with get_session() as session:
            existing = await session.get(ProjectRow, project_id)
            if existing is None:
                row = ProjectRow(
                    project_id=project_id,
                    user_id=uid,
                    topic=topic,
                    final_version=final_version,
                    project_summary=project_summary,
                    created_at=now,
                    updated_at=now,
                    last_accessed_at=now,
                )
                session.add(row)
            else:
                if uid and existing.user_id not in (None, uid):
                    return None
                existing.user_id = uid or existing.user_id
                existing.topic = topic or existing.topic
                existing.final_version = final_version
                existing.project_summary = project_summary
                existing.updated_at = now
                row = existing

            await session.commit()
            await session.refresh(row)
            return row

    async def get_project(self, project_id: str) -> ProjectRow | None:
        async with get_session() as session:
            return await session.get(ProjectRow, project_id)

    async def delete_project(self, project_id: str, *, user_id: str | None = None) -> bool:
        """删除指定用户的 project 及其 versions；不存在或不属于该用户时返回 False。"""
        project_id = (project_id or "").strip()
        uid = normalize_user_id(user_id)
        if not project_id or not uid:
            return False
        if not await self.project_accessible(project_id, uid):
            return False

        async with get_session() as session:
            project_row = await session.get(ProjectRow, project_id)
            version_count_result = await session.execute(
                select(func.count())
                .select_from(VersionRow)
                .where(VersionRow.project_id == project_id, VersionRow.user_id == uid)
            )
            version_count = int(version_count_result.scalar_one())
            if project_row is None and version_count == 0:
                return False
            if project_row is not None and project_row.user_id not in (None, uid):
                return False

            await session.execute(
                update(VersionRow)
                .where(VersionRow.project_id == project_id, VersionRow.user_id == uid)
                .values(parent_version_id=None)
            )
            await session.execute(
                delete(VersionRow).where(
                    VersionRow.project_id == project_id,
                    VersionRow.user_id == uid,
                )
            )
            if project_row is not None and project_row.user_id in (None, uid):
                await session.delete(project_row)
            await session.commit()
            return True


project_memory = ProjectMemoryService()
