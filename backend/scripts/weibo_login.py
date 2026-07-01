#!/usr/bin/env python3
"""用与后端相同的 browser-use Profile 交互式登录微博（一次性）。"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from app.services.social.browser_use_support import (
    close_weibo_browser_session,
    create_weibo_browser_session,
    get_focus_page_url,
    navigate_weibo_home,
    require_browser_use,
)
from app.services.social.profile_paths import resolve_weibo_profile_dir

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


async def main() -> None:
    profile_dir = resolve_weibo_profile_dir()
    print(f"Profile: {profile_dir}")
    print("将用 browser-use 打开浏览器，请完成微博登录/安全验证。")
    print("看到微博首页后回到终端按 Enter，再关闭浏览器。")

    require_browser_use()
    browser_session = await create_weibo_browser_session(headless=False)
    try:
        await navigate_weibo_home(browser_session)
        input("\n登录完成后按 Enter…")
        print("当前 URL:", await get_focus_page_url(browser_session))
    finally:
        await close_weibo_browser_session(browser_session)

    print("完成。可运行: curl -s http://127.0.0.1:8000/social/status | python3 -m json.tool")


if __name__ == "__main__":
    asyncio.run(main())
