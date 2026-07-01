"""微博自动化浏览器 Profile 路径解析。

browser-use 0.13 若路径名包含 ``chrome``，会把 Profile 复制到临时目录，
导致你在手动 Chrome 里的登录态无法被后续 Agent/Playwright 复用。
因此请使用不含 ``chrome`` 字样的目录名，例如 ``data/weibo-profile``。
"""

from __future__ import annotations

import logging
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

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
            "BROWSER_USE_PROFILE_PATH 路径含 chrome，browser-use 会复制到临时目录，"
            "登录态可能无法持久化。请改用例如 data/weibo-profile"
        )
    path.mkdir(parents=True, exist_ok=True)
    return resolved
