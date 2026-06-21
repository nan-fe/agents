"""飞书 OpenAPI 客户端：tenant / user token 与请求封装。"""

from __future__ import annotations

import time
from typing import Any, Literal

import httpx

from lark_im.settings import lark_settings

LarkIdentity = Literal["bot", "user"]

_TENANT_TOKEN_URL = (
    "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
)
_API_BASE = "https://open.feishu.cn/open-apis"


class LarkApiError(Exception):
    """飞书 API 返回业务错误。"""

    def __init__(self, code: int, msg: str, raw: Any = None) -> None:
        self.code = code
        self.msg = msg
        self.raw = raw
        super().__init__(f"Lark API error {code}: {msg}")


class LarkClient:
    """轻量 HTTP 客户端。"""

    def __init__(
        self,
        app_id: str | None = None,
        app_secret: str | None = None,
        user_access_token: str | None = None,
    ) -> None:
        self._app_id = (app_id or lark_settings.LARK_APP_ID or "").strip()
        self._app_secret = (app_secret or lark_settings.LARK_APP_SECRET or "").strip()
        self._user_access_token = (
            user_access_token or lark_settings.LARK_USER_ACCESS_TOKEN or ""
        ).strip()
        self._tenant_token: str | None = None
        self._tenant_token_expires_at: float = 0.0

    def _can_bot_auth(self) -> bool:
        return bool(self._app_id and self._app_secret)

    def _can_user_auth(self) -> bool:
        return bool(self._user_access_token)

    async def get_auth_status(self) -> dict[str, Any]:
        bot_ok = False
        bot_error: str | None = None
        if self._can_bot_auth():
            try:
                await self._get_tenant_access_token()
                bot_ok = True
            except Exception as exc:
                bot_error = str(exc)
        else:
            bot_error = "LARK_APP_ID / LARK_APP_SECRET 未配置"

        user_ok = self._can_user_auth()
        return {
            "bot": {
                "configured": self._can_bot_auth(),
                "available": bot_ok,
                "error": bot_error,
            },
            "user": {
                "configured": user_ok,
                "available": user_ok,
                "error": None if user_ok else "LARK_USER_ACCESS_TOKEN 未配置",
            },
            "default_identity": lark_settings.LARK_DEFAULT_IDENTITY,
        }

    async def _get_tenant_access_token(self) -> str:
        if (
            self._tenant_token
            and time.monotonic() < self._tenant_token_expires_at
        ):
            return self._tenant_token

        if not self._can_bot_auth():
            raise LarkApiError(0, "Bot 凭证未配置")

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                _TENANT_TOKEN_URL,
                json={"app_id": self._app_id, "app_secret": self._app_secret},
            )
            data = resp.json()

        if data.get("code") != 0:
            raise LarkApiError(
                int(data.get("code", -1)),
                str(data.get("msg", "tenant token failed")),
                data,
            )

        token = str(data.get("tenant_access_token", ""))
        expire = int(data.get("expire", 7200))
        self._tenant_token = token
        self._tenant_token_expires_at = time.monotonic() + max(expire - 60, 60)
        return token

    async def _access_token_for(self, identity: LarkIdentity) -> str:
        if identity == "user":
            if not self._can_user_auth():
                raise LarkApiError(0, "User access token 未配置")
            return self._user_access_token
        return await self._get_tenant_access_token()

    async def request(
        self,
        method: str,
        path: str,
        *,
        identity: LarkIdentity = "bot",
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        token = await self._access_token_for(identity)
        url = f"{_API_BASE}{path}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.request(
                method,
                url,
                headers=headers,
                params=params,
                json=json_body,
            )
            data = resp.json()

        if data.get("code") != 0:
            raise LarkApiError(
                int(data.get("code", -1)),
                str(data.get("msg", "request failed")),
                data,
            )
        return data
