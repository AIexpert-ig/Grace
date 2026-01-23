"""Configuration settings for the Grace AI Infrastructure application."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):  # pylint: disable=too-few-public-methods
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

    PROJECT_NAME: str = "Grace AI Infrastructure"
    TELEGRAM_BOT_TOKEN: str  # Required - no default
    TELEGRAM_CHAT_ID: str  # Required - no default
    API_KEY: str  # Required for webhook authentication (deprecated - use HMAC_SECRET)
    HMAC_SECRET: str  # Required for HMAC signature validation
    DATABASE_URL: str  # Required - PostgreSQL connection string
    
    # Database connection pool settings
    DB_POOL_SIZE: int = 20  # Number of connections to maintain in the pool
    DB_MAX_OVERFLOW: int = 10  # Maximum overflow connections beyond pool_size
    DB_POOL_TIMEOUT: int = 30  # Seconds to wait before giving up on getting a connection
    DB_POOL_RECYCLE: int = 3600  # Seconds before recycling a connection (1 hour)
    DB_POOL_PRE_PING: bool = True  # Verify connections before using them
    
    # Environment detection
    IS_SERVERLESS: bool = False  # Set to True for serverless environments (uses NullPool)


settings = Settings()
