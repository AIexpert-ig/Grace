"""Global pytest configuration for environment defaults."""
from __future__ import annotations

import os


def _set_test_env_defaults() -> None:
    """Ensure required Settings env vars exist for test imports."""
    defaults = {
        "TELEGRAM_BOT_TOKEN": "test_token",
        "TELEGRAM_CHAT_ID": "test_chat_id",
        "API_KEY": "test_api_key",
        "HMAC_SECRET": "test_hmac_secret_key_for_tests",
        "DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/grace_test_db",
        "TEST_DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/grace_test_db",
    }

    for key, value in defaults.items():
        os.environ.setdefault(key, value)


_set_test_env_defaults()
