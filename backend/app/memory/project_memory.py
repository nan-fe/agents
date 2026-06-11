"""Project Memory：versions 即时写入，projects 在 finalize 时汇总。"""
from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select

from app.memory.db import get_session
from app.memory.models import ProjectRow, VersionRow


def new_project_id() -> str:
    return f"proj_{uuid.uuid4().hex[:12]}"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def build_version_summary(intent: str, user_input: str, result: dict[str, Any]) -> str:
    title = (result.get("title") or "").strip()
    if title:
        return title[:120]
    snippet = (user_input or "").strip()[:60]
    return f"{intent or 'create'}: {snippet}" if snippet else intent or "version"


class ProjectMemoryService:
    async def create_project(self, *, user_id: str | None = None) -> str:
        """创建 project 并写入 projects 表（stub），便于 GET /projects 列表定位。"""
        project_id = new_project_id()
        now = _utcnow()
        async with get_session() as session:
            session.add(
                ProjectRow(
                    project_id=project_id,
                    user_id=user_id,
                    topic="",
                    final_version=None,
                    project_summary="",
                    created_at=now,
                    updated_at=now,
                    last_accessed_at=now,
                )
            )
            await session.commit()
        return project_id

    async def touch_project(self, project_id: str) -> None:
        """记录用户打开项目的时间，不影响 updated_at（内容变更时间）。"""
        async with get_session() as session:
            row = await session.get(ProjectRow, project_id)
            if row is None:
                return
            row.last_accessed_at = _utcnow()
            await session.commit()

    async def list_projects(self, *, user_id: str | None = None) -> list[ProjectRow]:
        async with get_session() as session:
            query = select(ProjectRow).order_by(
                ProjectRow.last_accessed_at.desc(),
                ProjectRow.created_at.desc(),
            )
            if user_id:
                query = query.where(ProjectRow.user_id == user_id)
            finalized = list((await session.execute(query)).scalars().all())

        finalized_ids = {row.project_id for row in finalized}
        orphan_items = await self._list_orphan_version_projects(
            exclude_ids=finalized_ids
        )
        return self._merge_project_lists(finalized, orphan_items)

    async def _list_orphan_version_projects(
        self, *, exclude_ids: set[str]
    ) -> list[ProjectRow]:
        """仅有 versions、尚未 finalize 的 project_id（兼容旧数据）。"""
        async with get_session() as session:
            rows = await session.execute(
                select(
                    VersionRow.project_id,
                    func.max(VersionRow.created_at),
                    func.count(),
                )
                .group_by(VersionRow.project_id)
                .order_by(func.max(VersionRow.created_at).desc())
            )

        orphans: list[ProjectRow] = []
        for project_id, latest_at, _count in rows.all():
            if project_id in exclude_ids:
                continue
            versions = await self.list_versions(project_id)
            if not versions:
                continue
            latest = versions[-1]
            planning = latest.planning or {}
            topic = (planning.get("topic") or "").strip() or (
                latest.result.get("title") or ""
            )
            summaries = [v.summary for v in versions if v.summary]
            orphans.append(
                ProjectRow(
                    project_id=project_id,
                    user_id=None,
                    topic=str(topic),
                    final_version=latest.version_label,
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

    async def version_count(self, project_id: str) -> int:
        async with get_session() as session:
            result = await session.execute(
                select(func.count())
                .select_from(VersionRow)
                .where(VersionRow.project_id == project_id)
            )
            return int(result.scalar_one())

    async def append_version(
        self,
        *,
        project_id: str,
        parent_version_id: str | None,
        intent: str,
        user_input: str,
        result: dict[str, Any],
        planning: dict[str, Any] | None,
    ) -> VersionRow:
        async with get_session() as session:
            count_result = await session.execute(
                select(func.count())
                .select_from(VersionRow)
                .where(VersionRow.project_id == project_id)
            )
            version_number = int(count_result.scalar_one()) + 1
            version_label = f"v{version_number}"
            version_id = f"ver_{secrets.token_urlsafe(9)}"
            summary = build_version_summary(intent, user_input, result)

            row = VersionRow(
                version_id=version_id,
                project_id=project_id,
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
            await session.commit()
            await session.refresh(row)
            return row

    async def list_versions(self, project_id: str) -> list[VersionRow]:
        async with get_session() as session:
            result = await session.execute(
                select(VersionRow)
                .where(VersionRow.project_id == project_id)
                .order_by(VersionRow.version_number.asc())
            )
            return list(result.scalars().all())

    async def get_latest_version(self, project_id: str) -> VersionRow | None:
        versions = await self.list_versions(project_id)
        return versions[-1] if versions else None

    async def finalize_project(
        self,
        project_id: str,
        *,
        user_id: str | None = None,
    ) -> ProjectRow | None:
        """将 versions 汇总写入 projects 表；无版本时返回 None。"""
        versions = await self.list_versions(project_id)
        if not versions:
            return None

        latest = versions[-1]
        planning = latest.planning or {}
        topic = (planning.get("topic") or "").strip()
        if not topic:
            topic = (latest.result.get("title") or "").strip()

        summaries = [v.summary for v in versions if v.summary]
        project_summary = " → ".join(summaries[-8:])

        now = _utcnow()
        async with get_session() as session:
            existing = await session.get(ProjectRow, project_id)
            if existing is None:
                row = ProjectRow(
                    project_id=project_id,
                    user_id=user_id,
                    topic=topic,
                    final_version=latest.version_label,
                    project_summary=project_summary,
                    created_at=now,
                    updated_at=now,
                    last_accessed_at=now,
                )
                session.add(row)
            else:
                existing.user_id = user_id or existing.user_id
                existing.topic = topic or existing.topic
                existing.final_version = latest.version_label
                existing.project_summary = project_summary
                existing.updated_at = now
                existing.last_accessed_at = now
                row = existing

            await session.commit()
            await session.refresh(row)
            return row

    async def get_project(self, project_id: str) -> ProjectRow | None:
        async with get_session() as session:
            return await session.get(ProjectRow, project_id)


project_memory = ProjectMemoryService()
