"""飞书 OAuth 与 DCR 测试。"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app
from app.memory.db import close_db, init_db
from app.services.lark_oauth_service import lark_oauth_registry
from lark_im.oauth import LarkOAuthService
from lark_im.settings import lark_settings


@pytest.fixture(autouse=True)
def memory_db(monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setattr(lark_settings, "LARK_APP_ID", "cli_test")
    monkeypatch.setattr(lark_settings, "LARK_APP_SECRET", "secret_test")
    monkeypatch.setattr(
        lark_settings,
        "LARK_OAUTH_REDIRECT_URI",
        "http://test/lark/oauth/callback",
    )


def test_build_authorize_url_contains_feishu_host() -> None:
    svc = LarkOAuthService(app_id="cli_test", app_secret="secret")
    url = svc.build_authorize_url(
        "http://test/lark/oauth/callback",
        "state-token",
        scope="offline_access",
    )
    assert "accounts.feishu.cn" in url
    assert "client_id=cli_test" in url
    assert "response_type=code" in url


async def _run_oauth_dcr_and_authorize() -> None:
    await close_db()
    await init_db()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        reg = await client.post(
            "/lark/oauth/register",
            json={
                "client_name": "test-client",
                "redirect_uris": ["http://localhost:3000/studio"],
            },
        )
        assert reg.status_code == 200
        body = reg.json()
        assert body["client_id"].startswith("oac_")
        assert body["client_secret"]

        with patch.object(
            lark_oauth_registry,
            "start_authorize",
            new=AsyncMock(
                return_value="https://accounts.feishu.cn/open-apis/authen/v1/authorize?x=1"
            ),
        ):
            auth = await client.get(
                "/lark/oauth/authorize",
                params={
                    "user_id": "demo",
                    "return_url": "http://localhost:3000/studio",
                    "client_id": body["client_id"],
                },
                follow_redirects=False,
            )
            assert auth.status_code == 302
            assert "accounts.feishu.cn" in auth.headers["location"]

    await close_db()


def test_oauth_register_and_authorize_redirect() -> None:
    asyncio.run(_run_oauth_dcr_and_authorize())
