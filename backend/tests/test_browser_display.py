"""browser_display 环境检测测试。"""

from __future__ import annotations

import pytest

from app.services.social import browser_display as bd


def test_linux_without_display_uses_browserless(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bd.sys, "platform", "linux")
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.delenv("SOCIAL_OAUTH_INTERACTIVE", raising=False)
    monkeypatch.delenv("SOCIAL_OAUTH_BROWSERLESS", raising=False)

    assert bd.has_interactive_display() is False
    assert bd.use_browserless_oauth() is True
    assert bd.resolve_login_headless() is True


def test_linux_desktop_display_is_interactive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bd.sys, "platform", "linux")
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.delenv("SOCIAL_OAUTH_BROWSERLESS", raising=False)

    assert bd.has_interactive_display() is True
    assert bd.use_browserless_oauth() is False
    assert bd.resolve_login_headless() is False


def test_xvfb_display_is_not_interactive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bd.sys, "platform", "linux")
    monkeypatch.setenv("DISPLAY", ":99")
    monkeypatch.delenv("SOCIAL_OAUTH_INTERACTIVE", raising=False)

    assert bd.has_interactive_display() is False
    assert bd.use_browserless_oauth() is True


def test_forced_browserless_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bd.sys, "platform", "darwin")
    monkeypatch.setenv("SOCIAL_OAUTH_BROWSERLESS", "1")

    assert bd.has_interactive_display() is False
    assert bd.use_browserless_oauth() is True
