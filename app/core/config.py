"""Configuration settings for the Grace AI Infrastructure application."""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):  # pylint: disable=too-few-public-methods
    """Application settings loaded from environment variables or defaults."""

    PROJECT_NAME: str = "Grace AI Infrastructure"
    TELEGRAM_BOT_TOKEN: str = "mock_token"
    TELEGRAM_CHAT_ID: str = "mock_chat_id"

    # In a real scenario, we might load these from a .env file
    # model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
