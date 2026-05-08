from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
import os


class Settings(BaseSettings):
    """应用配置管理"""

    SILICONFLOW_API_KEY: str
    SILICONFLOW_MODEL: str
    SILICONFLOW_BASE_URL: str
    COPYWRITE_MODEL: str
    EMBEDING_MODEL: str
    GENARATION_MODEL: str
    PLAN_MODEL: str
    INTENT_MODEL: str
    RANKER_MODEL: str
    # 图片生成配置
    IMAGE_MODEL: str
    REPLICATE_API_KEY: Optional[str] = None

    # 应用配置
    APP_NAME: str = "XHS Multi-Agent Creator"
    DEBUG: bool = True

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
