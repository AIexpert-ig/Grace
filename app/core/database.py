# app/core/database.py
"""Re-exports for backward compatibility.

The sync engine was removed. All DB access now goes through the async engine
and AsyncSessionLocal defined in app.db.
"""
import logging

from app.db import (  # noqa: F401 – re-exported for external consumers
    AsyncSessionLocal,
    Base,
    SessionLocal,
    async_engine as engine,
    get_db,
)

logger = logging.getLogger(__name__)


def get_pool_status() -> str:
    """Return a human-readable pool status string."""
    try:
        return engine.pool.status()
    except Exception:
        return "Uninitialized"
