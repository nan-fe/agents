"""MCP 服务独立配置（与 backend/app/config.py 的 LLM 等变量共用 .env）。"""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[1]
_BACKEND_DIR = _REPO_ROOT.parent / "backend"
_DEFAULT_ENV = _BACKEND_DIR / ".env"

if _DEFAULT_ENV.exists():
    load_dotenv(_DEFAULT_ENV, override=False)


class McpSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_DEFAULT_ENV) if _DEFAULT_ENV.exists() else None,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    MCP_HOST: str = "0.0.0.0"
    MCP_PORT: int = Field(default=3100, validation_alias="PORT")
    MCP_BEARER_TOKEN: str = Field(min_length=16)
    MCP_PATH: str = "/mcp"
    MCP_PRODUCTS_CSV: str | None = None
    MCP_WARM_RAG_ON_START: bool = True

    @property
    def backend_dir(self) -> Path:
        return _BACKEND_DIR

    @property
    def products_csv_path(self) -> str | None:
        if self.MCP_PRODUCTS_CSV:
            return self.MCP_PRODUCTS_CSV
        default = (
            _BACKEND_DIR
            / "app"
            / "agents"
            / "product_rag_system"
            / "data"
            / "taobao_products.csv"
        )
        if default.parent.exists():
            return str(default)
        return None

    @property
    def chroma_db_path(self) -> str:
        import os

        return os.environ.get(
            "CHROMA_DB_PATH",
            str(_BACKEND_DIR / "chroma_taobao_v1"),
        )


def load_settings() -> McpSettings:
    return McpSettings()
