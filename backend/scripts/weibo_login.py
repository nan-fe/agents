#!/usr/bin/env python3
"""用与后端相同的 Playwright Profile 交互式登录微博（一次性）。"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


async def main() -> None:
    from app.config import settings
    from app.services.social.profile_paths import resolve_weibo_profile_dir, weibo_profile_lock
    from app.services.social.weibo_publisher import _launch_context

    profile_dir = resolve_weibo_profile_dir()
    print(f"Profile: {profile_dir}")
    print("将用 Playwright 打开浏览器，请完成微博登录/安全验证。")
    print("看到微博首页后回到终端按 Enter，再关闭浏览器。")

    async with weibo_profile_lock:
        from playwright.async_api import async_playwright

        async with async_playwright() as playwright:
            context = await _launch_context(playwright, headless=False, for_login=True)
            pages = context.pages
            page = pages[0] if pages else await context.new_page()
            await page.goto(
                "https://weibo.com/",
                wait_until="domcontentloaded",
                timeout=settings.WEIBO_PUBLISH_TIMEOUT_MS,
            )
            await page.wait_for_timeout(1200)
            input("\n登录完成后按 Enter…")
            print("当前 URL:", page.url)
            await context.close()

    print(
        "完成。可运行: curl -s 'http://127.0.0.1:8000/social/status?force_refresh=true'"
        " | python3 -m json.tool"
    )


if __name__ == "__main__":
    asyncio.run(main())
