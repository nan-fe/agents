"""微博自动化浏览器 Profile 路径解析。

Playwright 持久化 Profile 路径名若包含 ``chrome``，部分工具会复制到临时目录，
导致登录态无法复用。请使用不含 ``chrome`` 字样的目录名，例如 ``data/weibo-profile``。
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

# Playwright 共用同一 Profile，任意时刻只允许一个会话持有。
weibo_profile_lock = asyncio.Lock()

_DEFAULT_RELATIVE = Path("data/weibo-profile")


def resolve_weibo_profile_dir() -> str:
    configured = (settings.BROWSER_USE_PROFILE_PATH or "").strip()
    if configured:
        path = Path(configured).expanduser()
    else:
        repo_root = Path(__file__).resolve().parents[4]
        path = repo_root / _DEFAULT_RELATIVE

    resolved = str(path.resolve())
    if "chrome" in resolved.lower():
        logger.warning(
            "BROWSER_USE_PROFILE_PATH 路径含 chrome，登录态可能无法持久化。"
            "请改用例如 data/weibo-profile"
        )
    path.mkdir(parents=True, exist_ok=True)
    return resolved
