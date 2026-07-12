"""微博登录态持久化（SQLite，按 Studio user_id）。"""

from __future__ import annotations

from datetime import UTC, datetime

from app.memory.db import get_session
from app.memory.models import WeiboAuthRow


async def save_weibo_auth(
    *,
    user_id: str,
    profile_path: str,
    logged_in: bool,
    current_url: str | None = None,
) -> None:
    uid = (user_id or "").strip()
    if not uid:
        raise ValueError("user_id 不能为空")
    now = datetime.now(UTC)
    async with get_session() as session:
        row = await session.get(WeiboAuthRow, uid)
        if row is None:
            row = WeiboAuthRow(
                id=uid,
                profile_path=profile_path,
                logged_in=logged_in,
                current_url=current_url,
                confirmed_at=now if logged_in else None,
                updated_at=now,
            )
            session.add(row)
        else:
            row.profile_path = profile_path
            row.logged_in = logged_in
            row.current_url = current_url
            row.confirmed_at = now if logged_in else None
            row.updated_at = now
        await session.commit()


async def get_weibo_auth(user_id: str) -> dict[str, object] | None:
    uid = (user_id or "").strip()
    if not uid:
        return None
    async with get_session() as session:
        row = await session.get(WeiboAuthRow, uid)
        if row is None:
            return None
        return {
            "profile_path": row.profile_path,
            "logged_in": row.logged_in,
            "current_url": row.current_url,
            "confirmed_at": row.confirmed_at.isoformat() if row.confirmed_at else None,
        }


async def clear_weibo_auth(user_id: str) -> None:
    uid = (user_id or "").strip()
    if not uid:
        return
    async with get_session() as session:
        row = await session.get(WeiboAuthRow, uid)
        if row is not None:
            row.logged_in = False
            row.current_url = None
            row.confirmed_at = None
            row.updated_at = datetime.now(UTC)
            await session.commit()
