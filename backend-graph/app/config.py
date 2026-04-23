from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置"""
    APP_NAME: str = "XHS Multi-Agent Creator API"
    DEBUG: bool = True
    
    # SiliconFlow API 配置
    SILICONFLOW_API_KEY: str = "sk-zbmufnvfvcxcfdjkjerosblljfarahlpjqdiperswadtpdqf"
    SILICONFLOW_BASE_URL: str = "https://api.siliconflow.cn/v1"
    SILICONFLOW_MODEL: str = "gpt-4-1106-preview"
    
    # 应用配置
    MAX_RETRY_ATTEMPTS: int = 3
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()