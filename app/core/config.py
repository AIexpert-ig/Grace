"""Configuration settings for the Grace AI Infrastructure application."""
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):  # pylint: disable=too-few-public-methods
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8", 
        case_sensitive=False,
        extra="ignore",  # Prevents crashing if extra variables are in .env
        fields={
            '_DATABASE_URL': {'env': 'DATABASE_URL'}  # Map DATABASE_URL env var to _DATABASE_URL field
        }
    )

    PROJECT_NAME: str = "Grace AI Infrastructure"
    
    # Defaults provided to prevent CI/Demo crashes
    TELEGRAM_BOT_TOKEN: str = "8534606686:AAHwAHq_zxuJJD66e85TC63kXosVO3bmM74"
    TELEGRAM_CHAT_ID: str = "8569555761"
    API_KEY: str = "grace_prod_key_99"
    HMAC_SECRET: str = "grace_hmac_secret_99"
    _DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/grace"
    
    @property
    def DATABASE_URL(self) -> str:
        """Transform Railway's postgresql:// to postgresql+asyncpg:// for async compatibility."""
        url = self._DATABASE_URL
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+asyncpg://", 1)
        return url
    
    # --- AI INTEGRATION ---
    OPENAI_API_KEY: str = "grace_prod_key_99"  # Add this for Grace's Neural Core
    
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