"""Orchestrator 飞书通知元数据测试。"""

from __future__ import annotations

import pytest

from lark_im.notify import build_lark_notification_meta
from lark_im.settings import lark_settings


@pytest.mark.parametrize(
    ("mode", "expected_mode"),
    [
        ("auto", "auto"),
        ("prompt", "prompt"),
        ("off", "off"),
        ("invalid", "auto"),
    ],
)
def test_build_lark_notification_meta_mode(
    monkeypatch, mode: str, expected_mode: str
) -> None:
    monkeypatch.setattr(lark_settings, "LARK_NOTIFY_MODE", mode)
    monkeypatch.setattr(lark_settings, "LARK_APP_ID", "cli_x")
    monkeypatch.setattr(lark_settings, "LARK_APP_SECRET", "sec")
    monkeypatch.setattr(lark_settings, "LARK_NOTIFY_CHAT_ID", "oc_x")

    meta = build_lark_notification_meta(
        review_passed=True,
        auto_sent=False,
        error="send failed",
    )
    assert meta["eligible"] is True
    assert meta["mode"] == expected_mode
    assert meta["configured"] is True
    assert meta["auto_sent"] is False
    assert meta["error"] == "send failed"
    assert meta["prompt"] == "审核已通过。是否推送到飞书？"


def test_build_lark_notification_meta_not_configured(monkeypatch) -> None:
    monkeypatch.setattr(lark_settings, "LARK_NOTIFY_MODE", "prompt")
    monkeypatch.setattr(lark_settings, "LARK_APP_ID", "")
    monkeypatch.setattr(lark_settings, "LARK_APP_SECRET", "")
    monkeypatch.setattr(lark_settings, "LARK_NOTIFY_CHAT_ID", "")

    meta = build_lark_notification_meta(review_passed=True)
    assert meta["configured"] is False
    assert meta["mode"] == "prompt"
