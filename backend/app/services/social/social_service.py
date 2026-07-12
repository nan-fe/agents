"""社交媒体发布编排服务。"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.config import settings
from app.services.social.content_adapter import build_weibo_payload, build_x_payload
from app.services.social.profile_paths import resolve_weibo_profile_dir, resolve_x_profile_dir
from app.services.social.publish_job_store import publish_job_store
from app.services.social.weibo_login_session import weibo_login_session_manager
from app.services.social.weibo_oauth_login_session import weibo_oauth_login_session_manager
from app.services.social.weibo_oauth_service import weibo_oauth_service
from app.services.social.weibo_publisher import check_weibo_login_state, publish_to_weibo
from app.services.social.x_login_session import x_login_session_manager
from app.services.social.x_oauth_login_session import x_oauth_login_session_manager
from app.services.social.x_oauth_service import x_oauth_service
from app.services.social.x_publisher import check_x_login_state, publish_to_x

logger = logging.getLogger(__name__)


def build_weibo_publish_meta(
    *,
    review_passed: bool,
    auto_started: bool = False,
    job_id: str | None = None,
    share_id: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    enabled = settings.WEIBO_PUBLISH_ENABLED
    auto = settings.WEIBO_PUBLISH_AUTO_ON_COMPLETE
    return {
        "eligible": bool(enabled and review_passed and auto),
        "enabled": enabled,
        "auto_on_complete": auto,
        "engine": "playwright",
        "auto_started": auto_started,
        "job_id": job_id,
        "share_id": share_id,
        "error": error,
    }


class SocialPublishService:
    async def get_weibo_user_status(
        self,
        user_id: str,
        *,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        uid = (user_id or "").strip()
        if not uid:
            raise ValueError("user_id 不能为空")

        if force_refresh and (
            await weibo_oauth_login_session_manager.has_active_session(uid)
            or await weibo_login_session_manager.has_active_session(uid)
        ):
            profile_state = {
                "configured": True,
                "logged_in": False,
                "reason": "连接进行中",
                "profile_path": resolve_weibo_profile_dir(uid),
                "user_id": uid,
            }
        else:
            profile_state = await check_weibo_login_state(user_id=uid, force_refresh=force_refresh)

        oauth_status = await weibo_oauth_service.user_status(
            uid,
            profile_logged_in=bool(profile_state.get("logged_in")),
        )
        oauth_status["profile"] = profile_state
        return oauth_status

    async def get_x_user_status(
        self, user_id: str, *, force_refresh: bool = False
    ) -> dict[str, Any]:
        uid = (user_id or "").strip()
        if not uid:
            raise ValueError("user_id 不能为空")

        if force_refresh and (
            await x_oauth_login_session_manager.has_active_session(uid)
            or await x_login_session_manager.has_active_session(uid)
        ):
            profile_state = {
                "configured": True,
                "logged_in": False,
                "reason": "连接进行中",
                "profile_path": resolve_x_profile_dir(uid),
                "user_id": uid,
            }
        else:
            profile_state = await check_x_login_state(user_id=uid, force_refresh=force_refresh)

        oauth_status = await x_oauth_service.user_status(
            uid,
            profile_logged_in=bool(profile_state.get("logged_in")),
        )
        oauth_status["profile"] = profile_state
        return oauth_status

    async def get_status(
        self,
        *,
        user_id: str = "",
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        uid = (user_id or "").strip()
        if uid:
            weibo = (await self.get_weibo_user_status(uid, force_refresh=force_refresh)).get(
                "profile", {}
            )
        else:
            weibo = {
                "configured": settings.WEIBO_PUBLISH_ENABLED,
                "logged_in": False,
                "reason": "未指定 user_id",
            }

        if uid:
            x_state = (await self.get_x_user_status(uid, force_refresh=force_refresh)).get(
                "profile", {}
            )
        else:
            x_state = {
                "configured": settings.X_PUBLISH_ENABLED,
                "logged_in": False,
                "reason": "未指定 user_id",
            }

        return {
            "weibo_publish_enabled": settings.WEIBO_PUBLISH_ENABLED,
            "weibo": weibo,
            "weibo_oauth_configured": weibo_oauth_service.is_configured(),
            "x_publish_enabled": settings.X_PUBLISH_ENABLED,
            "x": x_state,
            "x_oauth_configured": x_oauth_service.is_configured(),
            "x_sync_enabled": settings.X_SYNC_ENABLED,
            "x_sync_username": (settings.X_SYNC_USERNAME or "").strip() or None,
            "x_sync_interval_seconds": settings.X_SYNC_INTERVAL_SECONDS,
            "review_required": not settings.WEIBO_PUBLISH_SKIP_REVIEW,
            "x_review_required": not settings.X_PUBLISH_SKIP_REVIEW,
            "auto_on_complete": settings.WEIBO_PUBLISH_AUTO_ON_COMPLETE,
            "publish_engine": "playwright",
            "x_publish_engine": "playwright",
            "dry_run": settings.WEIBO_PUBLISH_DRY_RUN,
            "x_dry_run": settings.X_PUBLISH_DRY_RUN,
        }

    async def start_weibo_publish(
        self,
        *,
        user_id: str = "",
        title: str = "",
        content: str = "",
        hashtags: list[str] | None = None,
        image_url: str | None = None,
        share_url: str | None = None,
        review_approved: bool | None = None,
    ) -> str:
        if not settings.WEIBO_PUBLISH_ENABLED:
            raise ValueError("微博发布未启用")

        uid = (user_id or "").strip()
        if not uid:
            raise ValueError("user_id 不能为空")

        if not settings.WEIBO_PUBLISH_SKIP_REVIEW and review_approved is not True:
            raise ValueError("内容尚未审核通过，无法自动发布到微博")

        weibo_status = await self.get_weibo_user_status(uid)
        if not settings.WEIBO_PUBLISH_DRY_RUN and not weibo_status.get("connected"):
            if weibo_oauth_service.is_configured():
                raise ValueError("请先通过 OAuth 连接微博账号")
            raise ValueError("微博未登录，请先连接微博账号")

        payload = build_weibo_payload(
            title=title,
            content=content,
            hashtags=hashtags,
            image_url=image_url,
            share_url=share_url,
        )
        if not payload.text.strip():
            raise ValueError("发布正文不能为空")

        job = await publish_job_store.create_job(
            platform="weibo",
            payload_summary={
                "title": title,
                "text_preview": payload.text[:120],
                "has_image": bool(payload.image_url),
                "user_id": uid,
            },
        )

        async def _run() -> None:
            await publish_job_store.mark_running(job.job_id)

            async def on_progress(message: str) -> None:
                await publish_job_store.append_progress(job.job_id, message)

            screenshot_path: str | None = None
            try:
                post_url, screenshot_path = await publish_to_weibo(
                    payload,
                    user_id=uid,
                    on_progress=on_progress,
                )
                await publish_job_store.mark_succeeded(job.job_id, post_url=post_url)
            except Exception as exc:
                logger.exception("微博发布任务失败 job_id=%s", job.job_id)
                await publish_job_store.mark_failed(
                    job.job_id,
                    error=str(exc),
                    screenshot_path=screenshot_path,
                )

        asyncio.create_task(_run())
        return job.job_id

    async def start_x_publish(
        self,
        *,
        user_id: str = "",
        title: str = "",
        content: str = "",
        hashtags: list[str] | None = None,
        image_url: str | None = None,
        share_url: str | None = None,
        review_approved: bool | None = None,
    ) -> str:
        if not settings.X_PUBLISH_ENABLED:
            raise ValueError("X 发布未启用")

        uid = (user_id or "").strip()
        if not uid:
            raise ValueError("user_id 不能为空")

        if not settings.X_PUBLISH_SKIP_REVIEW and review_approved is not True:
            raise ValueError("内容尚未审核通过，无法自动发布到 X")

        x_status = await self.get_x_user_status(uid)
        if not settings.X_PUBLISH_DRY_RUN and not x_status.get("connected"):
            if x_oauth_service.is_configured():
                raise ValueError("请先通过 OAuth 连接 X 账号")
            raise ValueError("X 未登录，请先连接 X 账号")

        payload = build_x_payload(
            title=title,
            content=content,
            hashtags=hashtags,
            image_url=image_url,
            share_url=share_url,
        )
        if not payload.text.strip():
            raise ValueError("发布正文不能为空")

        job = await publish_job_store.create_job(
            platform="x",
            payload_summary={
                "title": title,
                "text_preview": payload.text[:120],
                "has_image": bool(payload.image_url),
                "user_id": uid,
            },
        )

        async def _run() -> None:
            await publish_job_store.mark_running(job.job_id)

            async def on_progress(message: str) -> None:
                await publish_job_store.append_progress(job.job_id, message)

            screenshot_path: str | None = None
            try:
                post_url, screenshot_path = await publish_to_x(
                    payload,
                    user_id=uid,
                    on_progress=on_progress,
                )
                await publish_job_store.mark_succeeded(job.job_id, post_url=post_url)
            except Exception as exc:
                logger.exception("X 发布任务失败 job_id=%s", job.job_id)
                await publish_job_store.mark_failed(
                    job.job_id,
                    error=str(exc),
                    screenshot_path=screenshot_path,
                )

        asyncio.create_task(_run())
        return job.job_id

    async def try_auto_publish_after_generation(
        self,
        result: dict[str, Any],
        *,
        review_passed: bool,
    ) -> dict[str, Any]:
        if not review_passed:
            return build_weibo_publish_meta(review_passed=False)
        return build_weibo_publish_meta(review_passed=True)

    async def get_job(self, job_id: str) -> dict[str, Any] | None:
        job = await publish_job_store.get_job(job_id)
        return job.to_dict() if job else None


_social_publish_service: SocialPublishService | None = None


def get_social_publish_service() -> SocialPublishService:
    global _social_publish_service
    if _social_publish_service is None:
        _social_publish_service = SocialPublishService()
    return _social_publish_service
