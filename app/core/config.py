"""Configuration settings for the Grace AI Infrastructure application."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):  # pylint: disable=too-few-public-methods
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

    PROJECT_NAME: str = "Grace AI Infrastructure"
    TELEGRAM_BOT_TOKEN: str  # Required - no default
    TELEGRAM_CHAT_ID: str  # Required - no default
    API_KEY: str  # Required for webhook authentication
    DATABASE_URL: str  # Required - PostgreSQL connection string


settings = Settings()
