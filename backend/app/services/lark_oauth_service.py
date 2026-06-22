"""飞书 OAuth 动态客户端注册 + 用户 token 持久化。"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from datetime import UTC, datetime, timedelta
from typing import Any

from app.memory.db import get_session
from app.memory.models import LarkOAuthClientRow, LarkUserTokenRow
from lark_im.oauth import LarkOAuthError, LarkOAuthService, LarkUserTokenBundle

_DEFAULT_STUDIO_CLIENT_ID = "oac_studio_default"
_STATE_TTL_SECONDS = 600


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _state_secret(app_secret: str) -> str:
    from lark_im.settings import lark_settings

    explicit = (lark_settings.LARK_OAUTH_STATE_SECRET or "").strip()
    if explicit:
        return explicit
    if app_secret:
        return app_secret
    return "lark-oauth-state"


def _sign_state(payload: dict[str, Any], secret: str) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    sig = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    raw = json.dumps({"payload": payload, "sig": sig})
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _verify_state(state: str, secret: str) -> dict[str, Any]:
    try:
        decoded = json.loads(base64.urlsafe_b64decode(state.encode()).decode())
        payload = decoded.get("payload")
        sig = decoded.get("sig")
        if not isinstance(payload, dict) or not isinstance(sig, str):
            raise LarkOAuthError("无效的 state")
        body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        expected = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            raise LarkOAuthError("state 签名校验失败")
        exp = float(payload.get("exp", 0))
        if exp and time.time() > exp:
            raise LarkOAuthError("state 已过期，请重新发起授权")
        return payload
    except LarkOAuthError:
        raise
    except Exception as exc:
        raise LarkOAuthError(f"无法解析 state: {exc}") from exc


class LarkOAuthRegistryService:
    def __init__(self) -> None:
        self._oauth = LarkOAuthService()

    @property
    def oauth(self) -> LarkOAuthService:
        return self._oauth

    async def register_client(
        self,
        *,
        client_name: str,
        redirect_uris: list[str],
        scopes: str | None = None,
    ) -> LarkOAuthClientRow:
        name = (client_name or "").strip() or "mcp-client"
        uris = [u.strip() for u in redirect_uris if (u or "").strip()]
        if not uris:
            raise ValueError("redirect_uris 不能为空")

        client_id = f"oac_{secrets.token_urlsafe(12)}"
        client_secret = secrets.token_urlsafe(32)
        now = _utcnow()

        row = LarkOAuthClientRow(
            client_id=client_id,
            client_secret=client_secret,
            client_name=name,
            redirect_uris=uris,
            scopes=(scopes or self._oauth.default_scopes()).strip(),
            created_at=now,
        )
        async with get_session() as session:
            session.add(row)
            await session.commit()
            await session.refresh(row)
        return row

    async def get_client(self, client_id: str) -> LarkOAuthClientRow | None:
        cid = (client_id or "").strip()
        if not cid:
            return None
        async with get_session() as session:
            return await session.get(LarkOAuthClientRow, cid)

    async def validate_client_redirect(self, client_id: str, return_url: str) -> LarkOAuthClientRow:
        client = await self.get_client(client_id)
        if client is None:
            raise LarkOAuthError(f"未注册的 OAuth 客户端: {client_id}")

        target = (return_url or "").strip()
        if not target:
            raise LarkOAuthError("return_url 不能为空")

        allowed = list(client.redirect_uris or [])
        if target not in allowed:
            raise LarkOAuthError(f"return_url 不在客户端允许列表中: {target}")
        return client

    async def seed_studio_default_client(
        self, redirect_uris: list[str]
    ) -> LarkOAuthClientRow | None:
        uris = [u.strip() for u in redirect_uris if (u or "").strip()]
        if not uris:
            return None

        async with get_session() as session:
            existing = await session.get(LarkOAuthClientRow, _DEFAULT_STUDIO_CLIENT_ID)
            if existing is not None:
                merged = sorted(set(existing.redirect_uris or []) | set(uris))
                existing.redirect_uris = merged
                await session.commit()
                await session.refresh(existing)
                return existing

            row = LarkOAuthClientRow(
                client_id=_DEFAULT_STUDIO_CLIENT_ID,
                client_secret=secrets.token_urlsafe(32),
                client_name="xhs-studio",
                redirect_uris=uris,
                scopes=self._oauth.default_scopes(),
                created_at=_utcnow(),
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row

    async def ensure_studio_default_client(
        self, extra_return_url: str | None = None
    ) -> LarkOAuthClientRow:
        from lark_im.settings import lark_settings

        configured = (lark_settings.LARK_OAUTH_STUDIO_REDIRECT_URIS or "").strip()
        uris = [u.strip() for u in configured.split(",") if u.strip()]
        extra = (extra_return_url or "").strip()
        if extra and extra not in uris:
            uris.append(extra)
        if not uris:
            raise LarkOAuthError("LARK_OAUTH_STUDIO_REDIRECT_URIS 未配置，无法发起 OAuth")
        return await self.seed_studio_default_client(uris)

    def feishu_callback_uri(self) -> str:
        from lark_im.settings import lark_settings

        uri = (lark_settings.LARK_OAUTH_REDIRECT_URI or "").strip()
        if not uri:
            raise LarkOAuthError(
                "LARK_OAUTH_REDIRECT_URI 未配置（飞书回调地址，需在开放平台重定向 URL 中登记）"
            )
        return uri

    async def start_authorize(
        self,
        *,
        client_id: str | None,
        user_id: str,
        return_url: str,
    ) -> str:
        if not self._oauth.is_configured():
            raise LarkOAuthError("飞书应用凭证未配置")

        cid = (client_id or "").strip() or _DEFAULT_STUDIO_CLIENT_ID
        if cid == _DEFAULT_STUDIO_CLIENT_ID:
            await self.ensure_studio_default_client(extra_return_url=return_url)
        client = await self.validate_client_redirect(cid, return_url)
        uid = (user_id or "").strip()
        if not uid:
            raise LarkOAuthError("user_id 不能为空")

        secret = _state_secret(self._oauth._app_secret)
        state_payload = {
            "client_id": client.client_id,
            "user_id": uid,
            "return_url": return_url,
            "nonce": secrets.token_urlsafe(8),
            "exp": time.time() + _STATE_TTL_SECONDS,
        }
        state = _sign_state(state_payload, secret)
        callback = self.feishu_callback_uri()
        return self._oauth.build_authorize_url(
            callback,
            state,
            scope=client.scopes,
        )

    async def complete_callback(self, code: str, state: str) -> str:
        if not code.strip():
            raise LarkOAuthError("缺少授权码 code")
        secret = _state_secret(self._oauth._app_secret)
        payload = _verify_state(state, secret)
        return_url = str(payload.get("return_url") or "").strip()
        user_id = str(payload.get("user_id") or "").strip()
        client_id = str(payload.get("client_id") or "").strip()
        if not return_url or not user_id:
            raise LarkOAuthError("state 缺少 return_url 或 user_id")

        await self.validate_client_redirect(client_id, return_url)
        callback = self.feishu_callback_uri()
        bundle = await self._oauth.exchange_code(code, callback)
        await self._store_user_token(user_id, bundle)
        return return_url

    async def _store_user_token(
        self, user_id: str, bundle: LarkUserTokenBundle
    ) -> LarkUserTokenRow:
        now = _utcnow()
        expires_at = now + timedelta(seconds=max(bundle.expires_in, 0))
        refresh_expires_at = None
        if bundle.refresh_expires_in:
            refresh_expires_at = now + timedelta(seconds=bundle.refresh_expires_in)

        async with get_session() as session:
            existing = await session.get(LarkUserTokenRow, user_id)
            if existing is None:
                row = LarkUserTokenRow(
                    user_id=user_id,
                    access_token=bundle.access_token,
                    refresh_token=bundle.refresh_token,
                    expires_at=expires_at,
                    refresh_expires_at=refresh_expires_at,
                    scope=bundle.scope,
                    updated_at=now,
                )
                session.add(row)
            else:
                existing.access_token = bundle.access_token
                existing.refresh_token = bundle.refresh_token or existing.refresh_token
                existing.expires_at = expires_at
                existing.refresh_expires_at = refresh_expires_at
                existing.scope = bundle.scope
                existing.updated_at = now
                row = existing

            await session.commit()
            await session.refresh(row)
            return row

    async def get_user_token_row(self, user_id: str) -> LarkUserTokenRow | None:
        uid = (user_id or "").strip()
        if not uid:
            return None
        async with get_session() as session:
            return await session.get(LarkUserTokenRow, uid)

    async def get_valid_user_access_token(self, user_id: str) -> str | None:
        row = await self.get_user_token_row(user_id)
        if row is None:
            return None

        now = _utcnow()
        if row.expires_at > now + timedelta(seconds=60):
            return row.access_token

        if not row.refresh_token:
            return None

        try:
            bundle = await self._oauth.refresh_access_token(row.refresh_token)
        except LarkOAuthError:
            return None

        updated = await self._store_user_token(user_id, bundle)
        return updated.access_token

    async def disconnect_user(self, user_id: str) -> bool:
        uid = (user_id or "").strip()
        if not uid:
            return False
        async with get_session() as session:
            row = await session.get(LarkUserTokenRow, uid)
            if row is None:
                return False
            await session.delete(row)
            await session.commit()
            return True

    async def user_status(self, user_id: str) -> dict[str, Any]:
        row = await self.get_user_token_row(user_id)
        if row is None:
            return {
                "connected": False,
                "user_id": user_id,
            }
        now = _utcnow()
        return {
            "connected": row.expires_at > now or bool(row.refresh_token),
            "user_id": user_id,
            "expires_at": row.expires_at.isoformat(),
            "has_refresh_token": bool(row.refresh_token),
            "scope": row.scope,
        }


lark_oauth_registry = LarkOAuthRegistryService()
