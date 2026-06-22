"""飞书 IM 配置（从环境变量 / .env 读取）。"""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

_PKG_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_ENV = _PKG_ROOT / ".env"

if _DEFAULT_ENV.exists():
    load_dotenv(_DEFAULT_ENV, override=False)


class LarkSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_DEFAULT_ENV) if _DEFAULT_ENV.exists() else None,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    LARK_APP_ID: str | None = None
    LARK_APP_SECRET: str | None = None
    LARK_NOTIFY_CHAT_ID: str | None = None
    LARK_NOTIFY_ENABLED: bool = False
    LARK_NOTIFY_MODE: str = "auto"
    LARK_DEFAULT_IDENTITY: str = "user"
    LARK_USER_ACCESS_TOKEN: str | None = None
    LARK_USE_CLI: bool | None = None
    LARK_CLI_PATH: str = "lark-cli"
    LARK_OAUTH_REDIRECT_URI: str | None = None
    LARK_OAUTH_SCOPES: str = "offline_access"
    LARK_OAUTH_STATE_SECRET: str | None = None
    LARK_OAUTH_STUDIO_REDIRECT_URIS: str | None = None


lark_settings = LarkSettings()
