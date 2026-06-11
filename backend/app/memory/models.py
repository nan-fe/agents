"""Project Memory ORM 模型。"""
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON, TypeDecorator


class Base(DeclarativeBase):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    """SQLite 存 UTC 无时区字符串；读出时补全为 timezone-aware UTC。"""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        else:
            value = value.astimezone(timezone.utc)
        return value.replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


_utc_datetime = UTCDateTime()


class ProjectRow(Base):
    __tablename__ = "projects"

    project_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    topic: Mapped[str] = mapped_column(Text, nullable=False, default="")
    final_version: Mapped[str | None] = mapped_column(String(16), nullable=True)
    project_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        _utc_datetime, nullable=False, default=_utcnow
    )
    # 内容变更时由业务代码显式写入（append_version / finalize 等），不用 onupdate。
    updated_at: Mapped[datetime] = mapped_column(
        _utc_datetime, nullable=False, default=_utcnow
    )
    # 用户最后一次打开该项目（GET /projects/{id}）；历史列表按此降序。
    last_accessed_at: Mapped[datetime] = mapped_column(
        _utc_datetime, nullable=False, default=_utcnow
    )


class VersionRow(Base):
    __tablename__ = "versions"
    __table_args__ = (
        UniqueConstraint("project_id", "version_number", name="uq_project_version_number"),
    )

    version_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    # project 行在 finalize 时才写入，此处不做 FK，避免先写 version 失败
    project_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    version_label: Mapped[str] = mapped_column(String(16), nullable=False)
    parent_version_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("versions.version_id"), nullable=True
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    result: Mapped[dict] = mapped_column(JSON, nullable=False)
    planning: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    intent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_input: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        _utc_datetime, nullable=False, default=_utcnow
    )
