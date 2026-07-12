"""X → 微博自动同步轮询。"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from pathlib import Path
from typing import Any

from app.config import settings
from app.services.social.content_adapter import extract_tweet_id_from_url
from app.services.social.social_service import get_social_publish_service

logger = logging.getLogger(__name__)

_SYNC_STORE = Path(__file__).resolve().parents[2] / "data" / "x_sync_state.json"


def _load_state() -> dict[str, Any]:
    if not _SYNC_STORE.exists():
        return {"synced_tweet_ids": [], "last_run_at": None, "last_error": None}
    try:
        return json.loads(_SYNC_STORE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"synced_tweet_ids": [], "last_run_at": None, "last_error": None}


def _save_state(state: dict[str, Any]) -> None:
    _SYNC_STORE.parent.mkdir(parents=True, exist_ok=True)
    _SYNC_STORE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


async def _fetch_latest_tweet_text(username: str) -> tuple[str, str] | None:
    """用 Playwright 读取 X 用户时间线最新一条推文。"""
    from app.services.social.profile_paths import resolve_x_profile_dir

    profile_dir = resolve_x_profile_dir(settings.X_SYNC_USERNAME or "sync")

    from playwright.async_api import async_playwright

    handle = username.lstrip("@")
    url = f"https://x.com/{handle}"

    async with async_playwright() as playwright:
        context = await playwright.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=settings.WEIBO_PUBLISH_HEADLESS,
            viewport={"width": 1280, "height": 900},
            locale="en-US",
        )
        page = context.pages[0] if context.pages else await context.new_page()
        await page.goto(
            url, wait_until="domcontentloaded", timeout=settings.WEIBO_PUBLISH_TIMEOUT_MS
        )
        await page.wait_for_timeout(2500)

        # 跳过登录墙
        if "login" in page.url.lower():
            await context.close()
            raise RuntimeError("X 未登录，请先在浏览器 Profile 中登录")

        articles = page.locator("article")
        count = await articles.count()
        if count == 0:
            await context.close()
            return None

        first = articles.first
        text = (await first.inner_text()).strip()
        link = first.locator("a[href*='/status/']").first
        href = ""
        if await link.count() > 0:
            href = await link.get_attribute("href") or ""
        await context.close()

        if not text:
            return None
        tweet_url = href if href.startswith("http") else f"https://x.com{href}"
        tweet_id = extract_tweet_id_from_url(tweet_url) or str(hash(text))
        return tweet_id, text


def _extract_image_urls_from_tweet(text: str) -> str | None:
    m = re.search(r"https?://\S+\.(?:jpg|jpeg|png|webp|gif)", text, re.I)
    return m.group(0) if m else None


async def run_x_sync_once() -> dict[str, Any]:
    """执行一次 X → 微博同步。"""
    if not settings.X_SYNC_ENABLED:
        return {"skipped": True, "reason": "X_SYNC_ENABLED=false"}

    username = (settings.X_SYNC_USERNAME or "").strip()
    if not username:
        return {"skipped": True, "reason": "未配置 X_SYNC_USERNAME"}

    state = _load_state()
    synced: set[str] = set(state.get("synced_tweet_ids") or [])

    try:
        latest = await _fetch_latest_tweet_text(username)
        if latest is None:
            state["last_run_at"] = time.time()
            state["last_error"] = None
            _save_state(state)
            return {"skipped": True, "reason": "未读取到推文"}

        tweet_id, text = latest
        if tweet_id in synced:
            state["last_run_at"] = time.time()
            state["last_error"] = None
            _save_state(state)
            return {"skipped": True, "reason": "无新推文", "tweet_id": tweet_id}

        service = get_social_publish_service()
        sync_user_id = (settings.WEIBO_SYNC_USER_ID or "").strip()
        if not sync_user_id:
            return {"skipped": True, "reason": "未配置 WEIBO_SYNC_USER_ID"}
        job_id = await service.start_weibo_publish(
            user_id=sync_user_id,
            title="",
            content=text,
            hashtags=None,
            image_url=_extract_image_urls_from_tweet(text),
            share_url=f"https://x.com/{username.lstrip('@')}/status/{tweet_id}",
            review_approved=True,
        )
        synced.add(tweet_id)
        # 保留最近 500 条
        state["synced_tweet_ids"] = list(synced)[-500:]
        state["last_run_at"] = time.time()
        state["last_error"] = None
        state["last_job_id"] = job_id
        _save_state(state)
        return {"synced": True, "tweet_id": tweet_id, "job_id": job_id}
    except Exception as exc:
        logger.exception("X 同步失败")
        state["last_run_at"] = time.time()
        state["last_error"] = str(exc)
        _save_state(state)
        return {"synced": False, "error": str(exc)}


async def x_sync_poller_loop() -> None:
    """后台周期任务：轮询 X 并同步到微博。"""
    interval = max(60.0, float(settings.X_SYNC_INTERVAL_SECONDS))
    while True:
        await asyncio.sleep(interval)
        if not settings.X_SYNC_ENABLED:
            continue
        try:
            result = await run_x_sync_once()
            if result.get("synced"):
                logger.info("X 同步已触发: %s", result)
        except Exception:
            logger.exception("X 同步轮询异常")
