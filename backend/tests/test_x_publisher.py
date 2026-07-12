"""X API 发布测试（Playwright）。"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from app.config import settings
from app.services.social.content_adapter import build_x_payload, format_x_text
from app.services.social.x_publisher import (
    _compose_intent_url,
    _is_login_url,
    _page_looks_logged_out,
    _post_shortcut,
    _select_all_shortcut,
    publish_to_x,
)


def test_select_all_shortcut_uses_platform_modifier() -> None:
    shortcut = _select_all_shortcut()
    assert shortcut in {"Meta+a", "Control+a"}


def test_post_shortcut_uses_platform_modifier() -> None:
    shortcut = _post_shortcut()
    assert shortcut in {"Meta+Enter", "Control+Enter"}


def test_compose_intent_url_encodes_text() -> None:
    url = _compose_intent_url("你好 #测试")
    assert url.startswith("https://x.com/intent/post?text=")
    assert "%E4%BD%A0%E5%A5%BD" in url


def test_is_login_url_ignores_backend_oauth_callback() -> None:
    callback = "http://localhost:8000/social/x/oauth/callback?code=abc&state=xyz"
    assert _is_login_url(callback) is False
    assert _page_looks_logged_out("<html><body>X 授权成功</body></html>", callback) is False


def test_is_login_url_detects_x_login_flow() -> None:
    assert _is_login_url("https://x.com/i/flow/login") is True
    assert _is_login_url("https://twitter.com/i/oauth2/authorize?client_id=x") is True


def test_format_x_text_truncates_to_280() -> None:
    long_body = "字" * 400
    text = format_x_text(content=long_body, max_chars=280)
    assert len(text) <= 280


def test_build_x_payload() -> None:
    payload = build_x_payload(
        title="标题",
        content="正文",
        hashtags=["测试"],
        share_url="https://example.com/s/1",
    )
    assert "#测试" in payload.text
    assert len(payload.text) <= 275


async def _run_publish_dry_run() -> None:
    settings.X_PUBLISH_ENABLED = True
    settings.X_PUBLISH_DRY_RUN = True
    payload = build_x_payload(title="T", content="C")
    progress: list[str] = []

    async def on_progress(message: str) -> None:
        progress.append(message)

    post_url, screenshot = await publish_to_x(payload, user_id="demo-user", on_progress=on_progress)
    assert post_url == "https://x.com/i/web/status/dry-run"
    assert screenshot is None
    assert any("DRY RUN" in line for line in progress)


def test_publish_to_x_dry_run() -> None:
    asyncio.run(_run_publish_dry_run())


async def _run_publish_playwright_success() -> None:
    settings.X_PUBLISH_ENABLED = True
    settings.X_PUBLISH_DRY_RUN = False
    payload = build_x_payload(content="hello world")

    with patch(
        "app.services.social.x_publisher._publish_via_playwright",
        AsyncMock(return_value=("https://x.com/home", None)),
    ):
        post_url, screenshot = await publish_to_x(payload, user_id="demo-user")
    assert post_url == "https://x.com/home"
    assert screenshot is None


def test_publish_to_x_playwright_success() -> None:
    asyncio.run(_run_publish_playwright_success())
