"""飞书 IM MCP Server 配置。"""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_PKG_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_ENV = _PKG_ROOT / ".env"

if _DEFAULT_ENV.exists():
    load_dotenv(_DEFAULT_ENV, override=False)


class McpSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_DEFAULT_ENV) if _DEFAULT_ENV.exists() else None,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    MCP_HOST: str = "0.0.0.0"
    MCP_PORT: int = Field(default=3101, validation_alias="PORT")
    MCP_BEARER_TOKEN: str = Field(min_length=16)
    MCP_PATH: str = "/mcp"


def load_settings() -> McpSettings:
    return McpSettings()
