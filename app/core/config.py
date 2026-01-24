"""Configuration settings for the Grace AI Infrastructure application."""
from pydantic_settings import BaseSettings, SettingsConfigDict  # pyright: ignore[reportMissingImports]


class Settings(BaseSettings):  # pylint: disable=too-few-public-methods
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

    PROJECT_NAME: str = "Grace AI Infrastructure"
    TELEGRAM_BOT_TOKEN: str  # Required - no default
    TELEGRAM_CHAT_ID: str  # Required - no default
    HMAC_SECRET: str  # Required for HMAC signature validation
    DATABASE_URL: str  # Required - PostgreSQL connection string
    
    # Property timezone - CRITICAL: Must match the physical location of the hotel
    PROPERTY_TIMEZONE: str = "Asia/Dubai"  # IANA timezone name (e.g., Asia/Dubai, America/New_York)
    
    # Database connection pool settings
    # WARNING: Each worker process creates its own pool!
    # Total connections = (DB_POOL_SIZE + DB_MAX_OVERFLOW) * NUM_WORKERS
    # Example: pool_size=5, max_overflow=2, 4 workers = (5+2)*4 = 28 connections
    # Ensure total doesn't exceed PostgreSQL max_connections (default: 100)
    DB_POOL_SIZE: int = 5  # Per-worker pool size (reduced from 20 for multi-worker safety)
    DB_MAX_OVERFLOW: int = 2  # Per-worker overflow (reduced from 10)
    DB_POOL_TIMEOUT: int = 30  # Seconds to wait before giving up on getting a connection
    DB_POOL_RECYCLE: int = 3600  # Seconds before recycling a connection (1 hour)
    DB_POOL_PRE_PING: bool = True  # Verify connections before using them
    
    # Worker configuration (for connection pool calculation)
    NUM_WORKERS: int = 1  # Number of Uvicorn/Gunicorn workers (set via deployment config)
    POSTGRES_MAX_CONNECTIONS: int = 100  # PostgreSQL max_connections setting
    
    # Environment detection
    IS_SERVERLESS: bool = False  # Set to True for serverless environments (uses NullPool)


settings = Settings()
