"""X (Twitter) OAuth 2.0 PKCE + 用户 token 持久化（连接身份，不用于 API 发帖）。"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

from app.config import settings
from app.memory.db import get_session
from app.memory.models import XUserTokenRow
from app.services.social.x_http import x_api_client

logger = logging.getLogger(__name__)

_STATE_TTL_SECONDS = 600
_AUTHORIZE_URL = "https://twitter.com/i/oauth2/authorize"
_TOKEN_URL = "https://api.twitter.com/2/oauth2/token"
_USERS_ME_URL = "https://api.twitter.com/2/users/me"


class XOAuthError(Exception):
    """X OAuth 流程错误。"""


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _state_secret() -> str:
    explicit = (settings.X_OAUTH_STATE_SECRET or "").strip()
    if explicit:
        return explicit
    secret = (settings.X_OAUTH_CLIENT_SECRET or "").strip()
    if secret:
        return secret
    return "x-oauth-state"


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
            raise XOAuthError("无效的 state")
        body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        expected = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            raise XOAuthError("state 签名校验失败")
        exp = float(payload.get("exp", 0))
        if exp and time.time() > exp:
            raise XOAuthError("state 已过期，请重新发起授权")
        return payload
    except XOAuthError:
        raise
    except Exception as exc:
        raise XOAuthError(f"无法解析 state: {exc}") from exc


def _pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)[:128]
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).decode().rstrip("=")
    return verifier, challenge


def _basic_auth_header() -> str:
    client_id = (settings.X_OAUTH_CLIENT_ID or "").strip()
    client_secret = (settings.X_OAUTH_CLIENT_SECRET or "").strip()
    if not client_id:
        raise XOAuthError("X_OAUTH_CLIENT_ID 未配置")
    if client_secret:
        raw = f"{client_id}:{client_secret}"
        return "Basic " + base64.b64encode(raw.encode()).decode()
    return ""


class XOAuthService:
    def is_configured(self) -> bool:
        return bool(
            settings.X_PUBLISH_ENABLED
            and (settings.X_OAUTH_CLIENT_ID or "").strip()
            and (settings.X_OAUTH_CALLBACK_URL or "").strip()
        )

    def callback_uri(self) -> str:
        uri = (settings.X_OAUTH_CALLBACK_URL or "").strip()
        if not uri:
            raise XOAuthError("X_OAUTH_CALLBACK_URL 未配置")
        return uri

    def default_scopes(self) -> str:
        return (settings.X_OAUTH_SCOPES or "users.read offline.access").strip()

    def build_authorize_url(self, *, state: str, code_challenge: str) -> str:
        client_id = (settings.X_OAUTH_CLIENT_ID or "").strip()
        if not client_id:
            raise XOAuthError("X_OAUTH_CLIENT_ID 未配置")
        params = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": self.callback_uri(),
            "scope": self.default_scopes(),
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        return f"{_AUTHORIZE_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str, code_verifier: str) -> dict[str, Any]:
        client_id = (settings.X_OAUTH_CLIENT_ID or "").strip()
        data = {
            "grant_type": "authorization_code",
            "code": code.strip(),
            "redirect_uri": self.callback_uri(),
            "code_verifier": code_verifier,
            "client_id": client_id,
        }
        headers: dict[str, str] = {"Content-Type": "application/x-www-form-urlencoded"}
        auth = _basic_auth_header()
        if auth:
            headers["Authorization"] = auth

        async with x_api_client(timeout=30.0) as client:
            resp = await client.post(_TOKEN_URL, data=data, headers=headers)
            if resp.status_code >= 400:
                logger.warning("X token exchange failed: %s %s", resp.status_code, resp.text)
                raise XOAuthError(f"换取 token 失败: {resp.text[:240]}")
            return resp.json()

    async def refresh_access_token(self, refresh_token: str) -> dict[str, Any]:
        client_id = (settings.X_OAUTH_CLIENT_ID or "").strip()
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token.strip(),
            "client_id": client_id,
        }
        headers: dict[str, str] = {"Content-Type": "application/x-www-form-urlencoded"}
        auth = _basic_auth_header()
        if auth:
            headers["Authorization"] = auth

        async with x_api_client(timeout=30.0) as client:
            resp = await client.post(_TOKEN_URL, data=data, headers=headers)
            if resp.status_code >= 400:
                logger.warning("X token refresh failed: %s %s", resp.status_code, resp.text)
                raise XOAuthError(f"刷新 token 失败: {resp.text[:240]}")
            return resp.json()

    async def fetch_user_profile(self, access_token: str) -> tuple[str | None, str | None]:
        headers = {"Authorization": f"Bearer {access_token}"}
        async with x_api_client(timeout=30.0) as client:
            resp = await client.get(
                _USERS_ME_URL,
                headers=headers,
                params={"user.fields": "username"},
            )
            if resp.status_code >= 400:
                logger.warning("X users/me failed: %s", resp.status_code)
                return None, None
            data = resp.json().get("data") or {}
            return str(data.get("id") or "") or None, str(data.get("username") or "") or None

    async def start_authorize(self, *, user_id: str, return_url: str = "") -> str:
        if not self.is_configured():
            raise XOAuthError("X OAuth 未配置（需 X_PUBLISH_ENABLED 与客户端凭证）")
        uid = (user_id or "").strip()
        if not uid:
            raise XOAuthError("user_id 不能为空")

        verifier, challenge = _pkce_pair()
        secret = _state_secret()
        state_payload = {
            "user_id": uid,
            "return_url": (return_url or "").strip(),
            "code_verifier": verifier,
            "nonce": secrets.token_urlsafe(8),
            "exp": time.time() + _STATE_TTL_SECONDS,
        }
        state = _sign_state(state_payload, secret)
        return self.build_authorize_url(state=state, code_challenge=challenge)

    async def complete_callback(self, code: str, state: str) -> str:
        if not code.strip():
            raise XOAuthError("缺少授权码 code")
        secret = _state_secret()
        payload = _verify_state(state, secret)
        user_id = str(payload.get("user_id") or "").strip()
        code_verifier = str(payload.get("code_verifier") or "").strip()
        if not user_id or not code_verifier:
            raise XOAuthError("state 缺少必要字段")

        token_data = await self.exchange_code(code, code_verifier)
        row = await self._store_user_token(user_id, token_data)
        return row.x_username or user_id

    async def _store_user_token(self, user_id: str, token_data: dict[str, Any]) -> XUserTokenRow:
        access_token = str(token_data.get("access_token") or "").strip()
        if not access_token:
            raise XOAuthError("token 响应缺少 access_token")

        refresh_token = str(token_data.get("refresh_token") or "").strip() or None
        expires_in = int(token_data.get("expires_in") or 7200)
        scope = str(token_data.get("scope") or "").strip() or None
        now = _utcnow()
        expires_at = now + timedelta(seconds=max(expires_in, 0))

        x_user_id, x_username = await self.fetch_user_profile(access_token)

        async with get_session() as session:
            existing = await session.get(XUserTokenRow, user_id)
            if existing is None:
                row = XUserTokenRow(
                    user_id=user_id,
                    access_token=access_token,
                    refresh_token=refresh_token,
                    expires_at=expires_at,
                    x_user_id=x_user_id,
                    x_username=x_username,
                    scope=scope,
                    updated_at=now,
                )
                session.add(row)
            else:
                existing.access_token = access_token
                if refresh_token:
                    existing.refresh_token = refresh_token
                existing.expires_at = expires_at
                if x_user_id:
                    existing.x_user_id = x_user_id
                if x_username:
                    existing.x_username = x_username
                existing.scope = scope
                existing.updated_at = now
                row = existing

            await session.commit()
            await session.refresh(row)
            return row

    async def get_user_token_row(self, user_id: str) -> XUserTokenRow | None:
        uid = (user_id or "").strip()
        if not uid:
            return None
        async with get_session() as session:
            return await session.get(XUserTokenRow, uid)

    async def disconnect_user(self, user_id: str) -> bool:
        uid = (user_id or "").strip()
        if not uid:
            return False
        async with get_session() as session:
            row = await session.get(XUserTokenRow, uid)
            if row is None:
                return False
            await session.delete(row)
            await session.commit()
            return True

    async def user_status(
        self, user_id: str, *, profile_logged_in: bool | None = None
    ) -> dict[str, Any]:
        profile_ready = profile_logged_in if profile_logged_in is not None else False
        row = await self.get_user_token_row(user_id)
        if row is None:
            # OAuth 未配置时，手动 Profile 登录即可视为已连接。
            connected = profile_ready if not self.is_configured() else False
            return {
                "connected": connected,
                "oauth_connected": False,
                "profile_ready": profile_ready,
                "user_id": user_id,
            }
        now = _utcnow()
        token_valid = row.expires_at > now or bool(row.refresh_token)
        if self.is_configured():
            connected = token_valid and profile_ready
        else:
            connected = profile_ready
        return {
            "connected": connected,
            "oauth_connected": token_valid,
            "profile_ready": profile_ready,
            "user_id": user_id,
            "x_user_id": row.x_user_id,
            "x_username": row.x_username,
            "expires_at": row.expires_at.isoformat(),
            "has_refresh_token": bool(row.refresh_token),
            "scope": row.scope,
        }


x_oauth_service = XOAuthService()
