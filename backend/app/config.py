from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
import os

_DEFAULT_MEMORY_DB = (
    Path(__file__).resolve().parent / "data" / "memory.db"
)


class Settings(BaseSettings):
    """应用配置管理"""

    API_KEY: str
    BASE_MODEL: str
    MODEL_BASE_URL: str
    COPYWRITE_MODEL: str
    EMBEDING_MODEL: str
    GENARATION_MODEL: str
    PLAN_MODEL: str
    INTENT_MODEL: str
    # 图片生成配置
    SILICONFLOW_API_KEY: str
    SILICONFLOW_BASE_URL: str
    IMAGE_MODEL: str
    REPLICATE_API_KEY: Optional[str] = None

    # 应用配置
    APP_NAME: str = "XHS Multi-Agent Creator"
    DEBUG: bool = True

    # Agent / 编排 LLM 调用分级超时（秒），避免慢节点拖死整条 SSE
    AGENT_TIMEOUT_INTENT_SECONDS: float = 20.0
    AGENT_TIMEOUT_ROUTING_SECONDS: float = 20.0
    AGENT_TIMEOUT_PLANNER_AGENT_SECONDS: float = 120.0
    AGENT_TIMEOUT_COPYWRITER_AGENT_SECONDS: float = 180.0
    AGENT_TIMEOUT_IMAGE_AGENT_SECONDS: float = 300.0
    AGENT_TIMEOUT_REVIEWER_AGENT_SECONDS: float = 90.0
    AGENT_TIMEOUT_RAG_AGENT_SECONDS: float = 120.0

    # 审核未通过后同轮自动修复
    REVIEW_REPAIR_MAX_ROUNDS: int = 1
    REVIEW_REPAIR_TOTAL_BUDGET_SECONDS: float = 600.0

    # SSE 断点续传缓冲：生成完成后保留时长（秒），超时后释放内存
    DIALOG_STREAM_RETENTION_SECONDS: float = 1800.0

    # 进程内 session_histories 空闲驱逐（秒）；0 表示关闭
    SESSION_IDLE_TTL_SECONDS: float = 1800.0

    # Project Memory（SQLite 默认；生产可改为 postgresql+asyncpg://...）
    DATABASE_URL: str = f"sqlite+aiosqlite:///{_DEFAULT_MEMORY_DB}"
    # 同时进行中的对话生成任务上限（Semaphore）；续传/回放不占槽位
    MAX_ACTIVE_DIALOG_GENERATIONS: int = 25

    # 意图/路由等外层有 wait_for 的编排 LLM：默认不重试，避免退避 sleep 先于外层超时触发「生成失败」
    LLM_ORCHESTRATION_HTTP_RETRY_MAX_ATTEMPTS: int = 1

    # LLM / 搜索 / 生图 HTTP 重试（策略化：仅可恢复错误 + 指数退避，见 retry_policy）
    LLM_HTTP_RETRY_MAX_ATTEMPTS: int = 3
    LLM_HTTP_RETRY_BASE_DELAY: float = 0.6
    LLM_HTTP_RETRY_MAX_DELAY: float = 24.0
    IMAGE_HTTP_RETRY_MAX_ATTEMPTS: int = 3
    IMAGE_HTTP_RETRY_BASE_DELAY: float = 1.0
    IMAGE_HTTP_RETRY_MAX_DELAY: float = 30.0
    IMAGE_GEN_TOTAL_BUDGET_SECONDS: float = 260.0
    SEARCH_HTTP_RETRY_MAX_ATTEMPTS: int = 3
    SEARCH_HTTP_RETRY_BASE_DELAY: float = 0.5
    SEARCH_HTTP_RETRY_MAX_DELAY: float = 12.0

    # 选品池商品页抓取
    PRODUCT_SCRAPER_USE_PLAYWRIGHT: bool = True
    PRODUCT_PLAYWRIGHT_TIMEOUT_MS: int = 35000
    PRODUCT_VISION_MODEL: Optional[str] = None

    # LangSmith
    LANGCHAIN_TRACING_V2: bool = True
    # Optional: LangSmith API key to access deployed graph
    LANGCHAIN_API_KEY: str
    LANGCHAIN_PROJECT: str

    model_config = SettingsConfigDict(
        # 1. 尝试读取 .env 文件，如果文件不存在则忽略而不报错
        env_file=".env" if os.path.exists(".env") else None,
        # 2. 区分大小写（保持你原有的逻辑）
        case_sensitive=True,
        # 3. 允许额外环境变量（防止因多余变量导致初始化失败）
        extra="ignore",
    )


# 创建全局配置实例
settings = Settings()
