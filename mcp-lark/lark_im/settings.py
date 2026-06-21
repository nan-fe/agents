"""飞书 IM 配置（从环境变量 / .env 读取）。"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

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

    LARK_APP_ID: Optional[str] = None
    LARK_APP_SECRET: Optional[str] = None
    LARK_NOTIFY_CHAT_ID: Optional[str] = None
    LARK_NOTIFY_ENABLED: bool = False
    LARK_DEFAULT_IDENTITY: str = "user"
    LARK_USER_ACCESS_TOKEN: Optional[str] = None
    LARK_USE_CLI: Optional[bool] = None
    LARK_CLI_PATH: str = "lark-cli"


lark_settings = LarkSettings()
