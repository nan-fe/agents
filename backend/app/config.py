from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """应用配置管理"""
    # SiliconFlow 配置
    SILICONFLOW_API_KEY: str
    SILICONFLOW_MODEL: str = "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B"
    SILICONFLOW_BASE_URL: str = "https://api.siliconflow.cn/v1"
    
    # 图片生成配置
    IMAGE_MODEL: str = "Kwai-Kolors/Kolors"  # free for dev
    REPLICATE_API_KEY: Optional[str] = None  # Stable Diffusion 使用
    
    # 应用配置
    APP_NAME: str = "XHS Multi-Agent Creator"
    DEBUG: bool = True
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# 创建全局配置实例
settings = Settings()
