import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Grace AI Infrastructure"
    TELEGRAM_BOT_TOKEN: str = "mock_token"
    TELEGRAM_CHAT_ID: str = "mock_chat_id"
    
    # In a real scenario, we might load these from a .env file
    # model_config = SettingsConfigDict(env_file=".env")

settings = Settings()
