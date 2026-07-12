#!/usr/bin/env python3
"""本地/服务器一次性 X Profile 登录（与后端共用 Profile 目录）。"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import settings  # noqa: E402
from app.services.social.browser_display import resolve_login_headless  # noqa: E402
from app.services.social.profile_paths import resolve_x_profile_dir  # noqa: E402
from app.services.social.x_publisher import _launch_context  # noqa: E402


async def main() -> None:
    user_id = (sys.argv[1] if len(sys.argv) > 1 else "demo").strip()
    if not user_id:
        raise SystemExit("usage: python scripts/x_login.py [user_id]")

    profile_dir = resolve_x_profile_dir(user_id)
    headless = resolve_login_headless(explicit=False)
    print(f"Profile: {profile_dir}")
    print(f"Headless: {headless} (set SOCIAL_OAUTH_INTERACTIVE=1 for visible browser on Linux)")

    from playwright.async_api import async_playwright

    async with async_playwright() as playwright:
        context = await _launch_context(
            playwright,
            user_id=user_id,
            headless=headless,
            for_login=True,
        )
        page = context.pages[0] if context.pages else await context.new_page()
        await page.goto(
            "https://x.com/i/flow/login",
            wait_until="domcontentloaded",
            timeout=settings.X_PUBLISH_TIMEOUT_MS,
        )
        print("请在浏览器中完成 X 登录，完成后按 Enter…")
        await asyncio.to_thread(sys.stdin.readline)
        await context.close()
        print("Profile 已保存。")


if __name__ == "__main__":
    asyncio.run(main())
