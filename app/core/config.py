"""Configuration settings for the Grace AI Infrastructure application."""
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):  # pylint: disable=too-few-public-methods
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8", 
        case_sensitive=False,
        extra="ignore"  # Prevents crashing if extra variables are in .env
    )

    PROJECT_NAME: str = "Grace AI Infrastructure"
    
    # Defaults provided to prevent CI/Demo crashes
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    API_KEY: str = ""
    HMAC_SECRET: str = ""
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/grace"
    
    # Property timezone - CRITICAL: Must match the physical location of the hotel
    PROPERTY_TIMEZONE: str = "Asia/Dubai"
    
    # Database connection pool settings
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 2
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 3600
    DB_POOL_PRE_PING: bool = True
    
    # Worker configuration
    NUM_WORKERS: int = 1
    POSTGRES_MAX_CONNECTIONS: int = 100
    
    # Environment detection
    IS_SERVERLESS: bool = False

settings = Settings()