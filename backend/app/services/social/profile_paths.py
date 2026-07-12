"""微博 / X 自动化浏览器 Profile 路径解析。

Playwright 持久化 Profile 路径名若包含 ``chrome``，部分工具会复制到临时目录，
导致登录态无法复用。请使用不含 ``chrome`` 字样的目录名，例如 ``data/weibo-profile``。
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

_CHROMIUM_LOCK_FILES = ("SingletonLock", "SingletonCookie", "lockfile")


def _lock_file_present(path: Path) -> bool:
    return path.is_symlink() or path.exists()


# Playwright 共用同一 Profile，任意时刻只允许一个会话持有。
weibo_profile_lock = asyncio.Lock()
x_profile_lock = asyncio.Lock()

_DEFAULT_WEIBO_RELATIVE = Path("data/weibo-profiles")
_DEFAULT_X_RELATIVE = Path("data/x-profiles")


def _sanitize_user_id(user_id: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in user_id.strip())
    return cleaned or "anonymous"


def resolve_weibo_profile_dir(user_id: str = "") -> str:
    uid = _sanitize_user_id(user_id)
    configured_root = (
        settings.WEIBO_PUBLISH_PROFILE_PATH or settings.BROWSER_USE_PROFILE_PATH or ""
    ).strip()
    if configured_root:
        root = Path(configured_root).expanduser()
        path = root if uid == "anonymous" and not user_id.strip() else root / uid
    else:
        repo_root = Path(__file__).resolve().parents[4]
        path = repo_root / _DEFAULT_WEIBO_RELATIVE / uid

    resolved = str(path.resolve())
    if "chrome" in resolved.lower():
        logger.warning(
            "微博 Profile 路径含 chrome，登录态可能无法持久化。请改用例如 data/weibo-profiles"
        )
    path.mkdir(parents=True, exist_ok=True)
    return resolved


def resolve_x_profile_dir(user_id: str = "") -> str:
    uid = _sanitize_user_id(user_id)
    configured_root = (
        settings.X_PUBLISH_PROFILE_PATH or settings.X_SYNC_PROFILE_PATH or ""
    ).strip()
    if configured_root:
        root = Path(configured_root).expanduser()
        path = root if uid == "anonymous" and not user_id.strip() else root / uid
    else:
        repo_root = Path(__file__).resolve().parents[4]
        path = repo_root / _DEFAULT_X_RELATIVE / uid

    resolved = str(path.resolve())
    if "chrome" in resolved.lower():
        logger.warning("X Profile 路径含 chrome，登录态可能无法持久化。请改用例如 data/x-profiles")
    path.mkdir(parents=True, exist_ok=True)
    return resolved


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    else:
        return True


def _parse_singleton_pid(lock_path: Path) -> int | None:
    try:
        if lock_path.is_symlink():
            target = os.readlink(lock_path)
        elif lock_path.exists():
            target = lock_path.read_text(encoding="utf-8", errors="ignore").strip()
        else:
            return None
        if "-" in target:
            return int(target.rsplit("-", 1)[-1])
    except (OSError, ValueError):
        return None
    return None


def clear_stale_chromium_profile_lock(profile_dir: str | Path) -> list[str]:
    """若 Chromium 锁文件对应进程已退出，则清理残留锁（常见于容器重启后）。"""
    root = Path(profile_dir)
    lock_path = root / "SingletonLock"
    if not any(_lock_file_present(root / name) for name in _CHROMIUM_LOCK_FILES):
        return []

    pid = _parse_singleton_pid(lock_path) if _lock_file_present(lock_path) else None
    if pid is not None and _pid_alive(pid):
        return []

    removed: list[str] = []
    for name in _CHROMIUM_LOCK_FILES:
        path = root / name
        if not _lock_file_present(path):
            continue
        try:
            path.unlink(missing_ok=True)
            removed.append(name)
        except OSError as exc:
            logger.warning("无法删除 Chromium 锁文件 %s: %s", path, exc)
    if removed:
        logger.info("已清理过期 Chromium Profile 锁: %s", ", ".join(removed))
    return removed
