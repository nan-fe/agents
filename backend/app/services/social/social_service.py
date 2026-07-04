"""社交媒体发布编排服务。"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.config import settings
from app.services.social.content_adapter import build_weibo_payload
from app.services.social.profile_paths import resolve_weibo_profile_dir
from app.services.social.publish_job_store import publish_job_store
from app.services.social.weibo_login_session import weibo_login_session_manager
from app.services.social.weibo_publisher import check_weibo_login_state, publish_to_weibo

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
    async def get_status(self, *, force_refresh: bool = False) -> dict[str, Any]:
        # 登录弹窗已占用 Profile 时，不再启动第二个浏览器做状态检测
        if force_refresh and await weibo_login_session_manager.has_active_session():
            profile_dir = resolve_weibo_profile_dir()
            weibo = {
                "configured": True,
                "logged_in": False,
                "reason": "登录进行中",
                "profile_path": profile_dir,
            }
        else:
            weibo = await check_weibo_login_state(force_refresh=force_refresh)
        return {
            "weibo_publish_enabled": settings.WEIBO_PUBLISH_ENABLED,
            "weibo": weibo,
            "x_sync_enabled": settings.X_SYNC_ENABLED,
            "x_sync_username": (settings.X_SYNC_USERNAME or "").strip() or None,
            "x_sync_interval_seconds": settings.X_SYNC_INTERVAL_SECONDS,
            "review_required": not settings.WEIBO_PUBLISH_SKIP_REVIEW,
            "auto_on_complete": settings.WEIBO_PUBLISH_AUTO_ON_COMPLETE,
            "publish_engine": "playwright",
            "dry_run": settings.WEIBO_PUBLISH_DRY_RUN,
        }

    async def start_weibo_publish(
        self,
        *,
        title: str = "",
        content: str = "",
        hashtags: list[str] | None = None,
        image_url: str | None = None,
        share_url: str | None = None,
        review_approved: bool | None = None,
    ) -> str:
        if not settings.WEIBO_PUBLISH_ENABLED:
            raise ValueError("微博发布未启用")

        if not settings.WEIBO_PUBLISH_SKIP_REVIEW and review_approved is not True:
            raise ValueError("内容尚未审核通过，无法自动发布到微博")

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

    async def try_auto_publish_after_generation(
        self,
        result: dict[str, Any],
        *,
        review_passed: bool,
    ) -> dict[str, Any]:
        """内容生成且审核通过后，仅返回微博发布 eligibility；实际发布由 Studio 弹窗确认。"""
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
