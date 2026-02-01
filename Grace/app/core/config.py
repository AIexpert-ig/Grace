"""Configuration settings for the Grace AI Infrastructure application."""
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):  # pylint: disable=too-few-public-methods
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8", 
        case_sensitive=False,
        extra="ignore"
    )

    PROJECT_NAME: str = "Grace AI Infrastructure"
    
    # SECURITY: Ensure these match your Railway Variables exactly
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    API_KEY: str = "grace_prod_key_99"
    HMAC_SECRET: str = "dubai_handshake_2026"  # Updated default to match our protocol
    
    # DATABASE
    database_url_raw: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/grace",
        validation_alias="DATABASE_URL"
    )
    
    @property
    def DATABASE_URL(self) -> str:
        url = self.database_url_raw
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+asyncpg://", 1)
        return url
    
    OPENAI_API_KEY: str = ""
    PROPERTY_TIMEZONE: str = "Asia/Dubai"
    
    # DB POOLING
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 2
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 3600
    DB_POOL_PRE_PING: bool = True
    
    NUM_WORKERS: int = 1
    POSTGRES_MAX_CONNECTIONS: int = 100
    IS_SERVERLESS: bool = False

settings = Settings()