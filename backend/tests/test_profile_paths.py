"""profile_paths 单元测试。"""

from __future__ import annotations

from unittest.mock import patch

from app.services.social.profile_paths import resolve_weibo_profile_dir


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
