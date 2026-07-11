"""profile_paths 单元测试。"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from app.services.social.profile_paths import (
    _parse_singleton_pid,
    clear_stale_chromium_profile_lock,
    resolve_weibo_profile_dir,
    resolve_x_profile_dir,
)


def test_resolve_x_profile_dir_per_user(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        __import__("app.services.social.profile_paths", fromlist=["settings"]).settings,
        "X_PUBLISH_PROFILE_PATH",
        str(tmp_path / "x-profiles"),
    )
    path_a = resolve_x_profile_dir("user-a")
    path_b = resolve_x_profile_dir("user-b")
    assert path_a != path_b
    assert path_a.endswith("user-a")
    assert path_b.endswith("user-b")


def test_resolve_weibo_profile_dir_warns_on_chrome_in_path(caplog) -> None:
    with patch.object(
        __import__("app.services.social.profile_paths", fromlist=["settings"]).settings,
        "BROWSER_USE_PROFILE_PATH",
        "/tmp/chrome-weibo-profile",
    ):
        path = resolve_weibo_profile_dir()
    assert path.endswith("chrome-weibo-profile")
    assert "chrome" in caplog.text.lower() or any(
        "chrome" in record.message.lower() for record in caplog.records
    )


def test_parse_singleton_pid_reads_hostname_suffix() -> None:
    assert _parse_singleton_pid(Path("408f3e2d2285-385")) is None
    lock = Path("/tmp/weibo-lock-test")
    lock.symlink_to("408f3e2d2285-385")
    try:
        assert _parse_singleton_pid(lock) == 385
    finally:
        lock.unlink()


def test_clear_stale_chromium_profile_lock_removes_dead_pid(tmp_path: Path) -> None:
    lock = tmp_path / "SingletonLock"
    lock.symlink_to(f"{os.uname().nodename}-999999")
    cookie = tmp_path / "SingletonCookie"
    cookie.write_text("stale", encoding="utf-8")

    removed = clear_stale_chromium_profile_lock(tmp_path)

    assert "SingletonLock" in removed
    assert "SingletonCookie" in removed
    assert not lock.exists()
    assert not cookie.exists()


def test_clear_stale_chromium_profile_lock_keeps_live_pid(tmp_path: Path, monkeypatch) -> None:
    lock = tmp_path / "SingletonLock"
    lock.symlink_to(f"{os.uname().nodename}-{os.getpid()}")

    removed = clear_stale_chromium_profile_lock(tmp_path)

    assert removed == []
    assert lock.is_symlink()
