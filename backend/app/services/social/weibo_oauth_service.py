"""微博 OAuth 2.0 + 用户 token 持久化（连接身份，不用于 API 发帖）。"""

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

import httpx

from app.config import settings
from app.memory.db import get_session
from app.memory.models import WeiboUserTokenRow

logger = logging.getLogger(__name__)

_STATE_TTL_SECONDS = 600
_AUTHORIZE_URL = "https://api.weibo.com/oauth2/authorize"
_TOKEN_URL = "https://api.weibo.com/oauth2/access_token"
_USERS_SHOW_URL = "https://api.weibo.com/2/users/show.json"


class WeiboOAuthError(Exception):
    """微博 OAuth 流程错误。"""


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _state_secret() -> str:
    explicit = (settings.WEIBO_OAUTH_STATE_SECRET or "").strip()
    if explicit:
        return explicit
    secret = (settings.WEIBO_OAUTH_CLIENT_SECRET or "").strip()
    if secret:
        return secret
    return "weibo-oauth-state"


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
            raise WeiboOAuthError("无效的 state")
        body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        expected = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            raise WeiboOAuthError("state 签名校验失败")
        exp = float(payload.get("exp", 0))
        if exp and time.time() > exp:
            raise WeiboOAuthError("state 已过期，请重新发起授权")
        return payload
    except WeiboOAuthError:
        raise
    except Exception as exc:
        raise WeiboOAuthError(f"无法解析 state: {exc}") from exc


class WeiboOAuthService:
    def is_configured(self) -> bool:
        return bool(
            settings.WEIBO_PUBLISH_ENABLED
            and (settings.WEIBO_OAUTH_CLIENT_ID or "").strip()
            and (settings.WEIBO_OAUTH_CLIENT_SECRET or "").strip()
            and (settings.WEIBO_OAUTH_CALLBACK_URL or "").strip()
        )

    def callback_uri(self) -> str:
        uri = (settings.WEIBO_OAUTH_CALLBACK_URL or "").strip()
        if not uri:
            raise WeiboOAuthError("WEIBO_OAUTH_CALLBACK_URL 未配置")
        return uri

    def build_authorize_url(self, *, state: str) -> str:
        client_id = (settings.WEIBO_OAUTH_CLIENT_ID or "").strip()
        if not client_id:
            raise WeiboOAuthError("WEIBO_OAUTH_CLIENT_ID 未配置")
        params = {
            "client_id": client_id,
            "response_type": "code",
            "redirect_uri": self.callback_uri(),
            "state": state,
        }
        return f"{_AUTHORIZE_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str) -> dict[str, Any]:
        client_id = (settings.WEIBO_OAUTH_CLIENT_ID or "").strip()
        client_secret = (settings.WEIBO_OAUTH_CLIENT_SECRET or "").strip()
        if not client_id or not client_secret:
            raise WeiboOAuthError("微博 OAuth 客户端凭证未配置")
        data = {
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "authorization_code",
            "code": code.strip(),
            "redirect_uri": self.callback_uri(),
        }
        async with httpx.AsyncClient(timeout=30.0, trust_env=False) as client:
            resp = await client.post(_TOKEN_URL, data=data)
            if resp.status_code >= 400:
                logger.warning("微博 token exchange failed: %s %s", resp.status_code, resp.text)
                raise WeiboOAuthError(f"换取 token 失败: {resp.text[:240]}")
            return resp.json()

    async def fetch_user_profile(
        self,
        access_token: str,
        weibo_uid: str,
    ) -> tuple[str | None, str | None]:
        async with httpx.AsyncClient(timeout=30.0, trust_env=False) as client:
            resp = await client.get(
                _USERS_SHOW_URL,
                params={"access_token": access_token, "uid": weibo_uid},
            )
            if resp.status_code >= 400:
                logger.warning("微博 users/show failed: %s", resp.status_code)
                return weibo_uid, None
            data = resp.json()
            return (
                str(data.get("id") or weibo_uid) or None,
                str(data.get("screen_name") or "") or None,
            )

    async def start_authorize(self, *, user_id: str, return_url: str = "") -> str:
        if not self.is_configured():
            raise WeiboOAuthError("微博 OAuth 未配置（需 WEIBO_PUBLISH_ENABLED 与客户端凭证）")
        uid = (user_id or "").strip()
        if not uid:
            raise WeiboOAuthError("user_id 不能为空")

        secret = _state_secret()
        state_payload = {
            "user_id": uid,
            "return_url": (return_url or "").strip(),
            "nonce": secrets.token_urlsafe(8),
            "exp": time.time() + _STATE_TTL_SECONDS,
        }
        state = _sign_state(state_payload, secret)
        return self.build_authorize_url(state=state)

    async def complete_callback(self, code: str, state: str) -> str:
        if not code.strip():
            raise WeiboOAuthError("缺少授权码 code")
        secret = _state_secret()
        payload = _verify_state(state, secret)
        user_id = str(payload.get("user_id") or "").strip()
        if not user_id:
            raise WeiboOAuthError("state 缺少 user_id")

        token_data = await self.exchange_code(code)
        row = await self._store_user_token(user_id, token_data)
        return row.weibo_screen_name or user_id

    async def _store_user_token(
        self,
        user_id: str,
        token_data: dict[str, Any],
    ) -> WeiboUserTokenRow:
        access_token = str(token_data.get("access_token") or "").strip()
        if not access_token:
            raise WeiboOAuthError("token 响应缺少 access_token")

        expires_in = int(token_data.get("expires_in") or 0)
        now = _utcnow()
        if expires_in > 0:
            expires_at = now + timedelta(seconds=expires_in)
        else:
            expires_at = now + timedelta(days=3650)

        weibo_uid = str(token_data.get("uid") or "").strip() or None
        weibo_uid, weibo_screen_name = await self.fetch_user_profile(
            access_token,
            weibo_uid or "",
        )

        async with get_session() as session:
            existing = await session.get(WeiboUserTokenRow, user_id)
            if existing is None:
                row = WeiboUserTokenRow(
                    user_id=user_id,
                    access_token=access_token,
                    expires_at=expires_at,
                    weibo_uid=weibo_uid,
                    weibo_screen_name=weibo_screen_name,
                    updated_at=now,
                )
                session.add(row)
            else:
                existing.access_token = access_token
                existing.expires_at = expires_at
                if weibo_uid:
                    existing.weibo_uid = weibo_uid
                if weibo_screen_name:
                    existing.weibo_screen_name = weibo_screen_name
                existing.updated_at = now
                row = existing

            await session.commit()
            await session.refresh(row)
            return row

    async def get_user_token_row(self, user_id: str) -> WeiboUserTokenRow | None:
        uid = (user_id or "").strip()
        if not uid:
            return None
        async with get_session() as session:
            return await session.get(WeiboUserTokenRow, uid)

    async def disconnect_user(self, user_id: str) -> bool:
        uid = (user_id or "").strip()
        if not uid:
            return False
        async with get_session() as session:
            row = await session.get(WeiboUserTokenRow, uid)
            if row is None:
                return False
            await session.delete(row)
            await session.commit()
            return True

    async def user_status(
        self,
        user_id: str,
        *,
        profile_logged_in: bool | None = None,
    ) -> dict[str, Any]:
        profile_ready = profile_logged_in if profile_logged_in is not None else False
        row = await self.get_user_token_row(user_id)
        if row is None:
            connected = profile_ready if not self.is_configured() else False
            return {
                "connected": connected,
                "oauth_connected": False,
                "profile_ready": profile_ready,
                "user_id": user_id,
            }
        now = _utcnow()
        token_valid = row.expires_at > now
        if self.is_configured():
            connected = token_valid and profile_ready
        else:
            connected = profile_ready
        return {
            "connected": connected,
            "oauth_connected": token_valid,
            "profile_ready": profile_ready,
            "user_id": user_id,
            "weibo_uid": row.weibo_uid,
            "weibo_screen_name": row.weibo_screen_name,
            "expires_at": row.expires_at.isoformat(),
            "scope": row.scope,
        }


weibo_oauth_service = WeiboOAuthService()
