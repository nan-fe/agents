"""飞书用户 OAuth 2.0（授权页跳转 + code 换 token）。"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx

from lark_im.settings import lark_settings

FEISHU_AUTHORIZE_URL = "https://accounts.feishu.cn/open-apis/authen/v1/authorize"
FEISHU_TOKEN_URL = "https://open.feishu.cn/open-apis/authen/v2/oauth/token"


@dataclass
class LarkUserTokenBundle:
    access_token: str
    expires_in: int
    refresh_token: str | None = None
    refresh_expires_in: int | None = None
    scope: str | None = None
    token_type: str = "Bearer"
    obtained_at: float = 0.0

    @property
    def expires_at(self) -> float:
        return self.obtained_at + max(self.expires_in, 0)

    def is_expired(self, skew_seconds: float = 60.0) -> bool:
        return time.monotonic() >= self.expires_at - skew_seconds


class LarkOAuthError(Exception):
    def __init__(self, message: str, *, code: int | None = None, raw: Any = None) -> None:
        self.code = code
        self.raw = raw
        super().__init__(message)


class LarkOAuthService:
    """飞书 OAuth 授权码流程（网页唤起飞书授权页）。"""

    def __init__(
        self,
        app_id: str | None = None,
        app_secret: str | None = None,
    ) -> None:
        self._app_id = (app_id or lark_settings.LARK_APP_ID or "").strip()
        self._app_secret = (app_secret or lark_settings.LARK_APP_SECRET or "").strip()

    def is_configured(self) -> bool:
        return bool(self._app_id and self._app_secret)

    def default_scopes(self) -> str:
        return (lark_settings.LARK_OAUTH_SCOPES or "offline_access").strip()

    def build_authorize_url(
        self,
        redirect_uri: str,
        state: str,
        *,
        scope: str | None = None,
    ) -> str:
        if not self.is_configured():
            raise LarkOAuthError("LARK_APP_ID / LARK_APP_SECRET 未配置")

        callback = (redirect_uri or "").strip()
        if not callback:
            raise LarkOAuthError("redirect_uri 不能为空")

        params = {
            "client_id": self._app_id,
            "response_type": "code",
            "redirect_uri": callback,
            "state": state,
        }
        scope_text = (scope or self.default_scopes()).strip()
        if scope_text:
            params["scope"] = scope_text

        return f"{FEISHU_AUTHORIZE_URL}?{urlencode(params)}"

    async def exchange_code(
        self,
        code: str,
        redirect_uri: str,
    ) -> LarkUserTokenBundle:
        return await self._token_request(
            {
                "grant_type": "authorization_code",
                "client_id": self._app_id,
                "client_secret": self._app_secret,
                "code": code.strip(),
                "redirect_uri": redirect_uri.strip(),
            }
        )

    async def refresh_access_token(self, refresh_token: str) -> LarkUserTokenBundle:
        return await self._token_request(
            {
                "grant_type": "refresh_token",
                "client_id": self._app_id,
                "client_secret": self._app_secret,
                "refresh_token": refresh_token.strip(),
            }
        )

    async def _token_request(self, body: dict[str, str]) -> LarkUserTokenBundle:
        if not self.is_configured():
            raise LarkOAuthError("LARK_APP_ID / LARK_APP_SECRET 未配置")

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                FEISHU_TOKEN_URL,
                json=body,
                headers={"Content-Type": "application/json; charset=utf-8"},
            )
            payload = resp.json()

        code = payload.get("code")
        if code is not None and int(code) != 0:
            raise LarkOAuthError(
                str(payload.get("msg") or "token exchange failed"),
                code=int(code),
                raw=payload,
            )

        data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        access = str(data.get("access_token") or "").strip()
        if not access:
            raise LarkOAuthError("响应缺少 access_token", raw=payload)

        expires_in = int(data.get("expires_in") or data.get("expire") or 7200)
        refresh = data.get("refresh_token")
        refresh_expires = data.get("refresh_token_expires_in") or data.get(
            "refresh_expires_in"
        )

        return LarkUserTokenBundle(
            access_token=access,
            expires_in=expires_in,
            refresh_token=str(refresh).strip() if refresh else None,
            refresh_expires_in=int(refresh_expires) if refresh_expires else None,
            scope=str(data.get("scope") or "") or None,
            token_type=str(data.get("token_type") or "Bearer"),
            obtained_at=time.monotonic(),
        )
