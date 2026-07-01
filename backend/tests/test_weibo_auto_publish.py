"""生成完成后的微博发布 eligibility 元数据。"""

from __future__ import annotations

import asyncio
from unittest.mock import patch

from app.config import settings
from app.services.social.social_service import (
    SocialPublishService,
    build_weibo_publish_meta,
)


def test_build_weibo_publish_meta() -> None:
    with patch.object(settings, "WEIBO_PUBLISH_ENABLED", False):
        with patch.object(settings, "WEIBO_PUBLISH_AUTO_ON_COMPLETE", True):
            meta = build_weibo_publish_meta(
                review_passed=True,
                auto_started=True,
                job_id="abc",
                share_id="share1",
            )
    assert meta["eligible"] is False
    assert meta["enabled"] is False
    assert meta["auto_on_complete"] is True
    assert meta["auto_started"] is True
    assert meta["job_id"] == "abc"


def test_try_auto_publish_after_generation_disabled() -> None:
    async def _run() -> None:
        service = SocialPublishService()
        settings.WEIBO_PUBLISH_ENABLED = False
        meta = await service.try_auto_publish_after_generation(
            {"title": "t", "content": "c", "review_approved": True},
            review_passed=True,
        )
        assert meta["eligible"] is False

    asyncio.run(_run())


def test_try_auto_publish_returns_eligibility_only() -> None:
    async def _run() -> None:
        settings.WEIBO_PUBLISH_ENABLED = True
        settings.WEIBO_PUBLISH_AUTO_ON_COMPLETE = True
        settings.WEIBO_PUBLISH_SKIP_REVIEW = False
        service = SocialPublishService()
        meta = await service.try_auto_publish_after_generation(
            {
                "title": "标题",
                "content": "正文",
                "hashtags": ["测试"],
                "review_approved": True,
            },
            review_passed=True,
        )
        assert meta["eligible"] is True
        assert meta["auto_started"] is False
        assert meta.get("job_id") is None
        assert meta.get("share_id") is None

    asyncio.run(_run())
