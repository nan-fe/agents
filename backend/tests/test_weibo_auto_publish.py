"""生成完成后的微博发布 eligibility 元数据。"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from app.config import settings
from app.services.social.social_service import (
    SocialPublishService,
    build_weibo_publish_meta,
)
from app.services.social.weibo_publisher import (
    check_weibo_login_state,
    invalidate_weibo_login_state_cache,
)


def test_check_weibo_login_state_skips_browser_without_force_refresh() -> None:
    async def _run() -> None:
        invalidate_weibo_login_state_cache()
        settings.WEIBO_PUBLISH_ENABLED = True
        settings.WEIBO_PUBLISH_DRY_RUN = False
        mock_browser = AsyncMock()
        with patch(
            "app.services.social.weibo_publisher.get_weibo_auth",
            AsyncMock(return_value=None),
        ):
            with patch(
                "app.services.social.weibo_publisher._check_weibo_login_state_playwright",
                mock_browser,
            ):
                result = await check_weibo_login_state(user_id="demo", force_refresh=False)
        assert result["logged_in"] is False
        assert result["reason"] == "未检测"
        mock_browser.assert_not_called()

    asyncio.run(_run())


def test_check_weibo_login_state_uses_playwright_on_force_refresh() -> None:
    async def _run() -> None:
        invalidate_weibo_login_state_cache()
        settings.WEIBO_PUBLISH_ENABLED = True
        settings.WEIBO_PUBLISH_DRY_RUN = False
        mock_result = {
            "configured": True,
            "logged_in": True,
            "current_url": "https://weibo.com/",
            "profile_path": "/tmp/weibo-profile",
            "driver": "playwright",
        }
        mock_browser = AsyncMock(return_value=mock_result)
        with patch(
            "app.services.social.weibo_publisher.get_weibo_auth",
            AsyncMock(return_value=None),
        ):
            with patch(
                "app.services.social.weibo_publisher._check_weibo_login_state_playwright",
                mock_browser,
            ):
                with patch(
                    "app.services.social.weibo_auth_store.save_weibo_auth",
                    AsyncMock(),
                ):
                    result = await check_weibo_login_state(user_id="demo", force_refresh=True)
        assert result["logged_in"] is True
        mock_browser.assert_awaited_once()

    asyncio.run(_run())


def test_check_weibo_login_state_uses_db_when_confirmed() -> None:
    async def _run() -> None:
        invalidate_weibo_login_state_cache()
        settings.WEIBO_PUBLISH_ENABLED = True
        settings.WEIBO_PUBLISH_DRY_RUN = False
        mock_browser = AsyncMock()
        with patch(
            "app.services.social.weibo_publisher.resolve_weibo_profile_dir",
            return_value="/tmp/weibo-profile",
        ):
            with patch(
                "app.services.social.weibo_publisher.get_weibo_auth",
                AsyncMock(
                    return_value={
                        "logged_in": True,
                        "profile_path": "/tmp/weibo-profile",
                        "current_url": "https://weibo.com/",
                        "confirmed_at": "2026-01-01T00:00:00+00:00",
                    },
                ),
            ):
                with patch(
                    "app.services.social.weibo_publisher._check_weibo_login_state_playwright",
                    mock_browser,
                ):
                    result = await check_weibo_login_state(user_id="demo", force_refresh=False)
        assert result["logged_in"] is True
        mock_browser.assert_not_called()

    asyncio.run(_run())


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
