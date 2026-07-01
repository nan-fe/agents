"""社交媒体发布编排服务。"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.config import settings
from app.services.social.content_adapter import build_weibo_payload
from app.services.social.publish_job_store import publish_job_store
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
    engine = (settings.WEIBO_PUBLISH_ENGINE or "browser_use").strip()
    return {
        "eligible": bool(enabled and review_passed and auto),
        "enabled": enabled,
        "auto_on_complete": auto,
        "engine": engine,
        "auto_started": auto_started,
        "job_id": job_id,
        "share_id": share_id,
        "error": error,
    }


class SocialPublishService:
    async def get_status(self) -> dict[str, Any]:
        weibo = await check_weibo_login_state()
        return {
            "weibo_publish_enabled": settings.WEIBO_PUBLISH_ENABLED,
            "weibo": weibo,
            "x_sync_enabled": settings.X_SYNC_ENABLED,
            "x_sync_username": (settings.X_SYNC_USERNAME or "").strip() or None,
            "x_sync_interval_seconds": settings.X_SYNC_INTERVAL_SECONDS,
            "review_required": not settings.WEIBO_PUBLISH_SKIP_REVIEW,
            "auto_on_complete": settings.WEIBO_PUBLISH_AUTO_ON_COMPLETE,
            "publish_engine": (settings.WEIBO_PUBLISH_ENGINE or "browser_use").strip(),
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
        """内容生成且审核通过后，自动创建分享快照并启动微博发布任务。"""
        if not review_passed:
            return build_weibo_publish_meta(review_passed=False)
        if not settings.WEIBO_PUBLISH_ENABLED or not settings.WEIBO_PUBLISH_AUTO_ON_COMPLETE:
            return build_weibo_publish_meta(review_passed=True)

        share_id: str | None = None
        try:
            from app.models.schemas import ShareCreateRequest
            from app.services.share_service import share_store

            snapshot = share_store.create_share(
                ShareCreateRequest(
                    title=str(result.get("title") or ""),
                    content=str(result.get("content") or ""),
                    hashtags=list(result.get("hashtags") or []),
                    image_url=result.get("image_url"),
                    message=result.get("message"),
                )
            )
            share_id = snapshot.id
        except Exception as exc:
            logger.warning("自动发布：创建分享快照失败: %s", exc)
            return build_weibo_publish_meta(
                review_passed=True,
                error=f"创建分享快照失败: {exc}",
            )

        try:
            job_id = await self.start_weibo_publish(
                title=str(result.get("title") or ""),
                content=str(result.get("content") or ""),
                hashtags=result.get("hashtags"),
                image_url=result.get("image_url"),
                share_url=f"/share/{share_id}" if share_id else None,
                review_approved=True,
            )
            return build_weibo_publish_meta(
                review_passed=True,
                auto_started=True,
                job_id=job_id,
                share_id=share_id,
            )
        except Exception as exc:
            logger.warning("自动微博发布启动失败: %s", exc)
            return build_weibo_publish_meta(
                review_passed=True,
                share_id=share_id,
                error=str(exc),
            )

    async def get_job(self, job_id: str) -> dict[str, Any] | None:
        job = await publish_job_store.get_job(job_id)
        return job.to_dict() if job else None


_social_publish_service: SocialPublishService | None = None


def get_social_publish_service() -> SocialPublishService:
    global _social_publish_service
    if _social_publish_service is None:
        _social_publish_service = SocialPublishService()
    return _social_publish_service
