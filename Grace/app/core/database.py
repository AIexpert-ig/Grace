# app/core/database.py
import os
import logging

from app.db import SessionLocal, get_engine, Base

logger = logging.getLogger(__name__)

# Fallback for local development or testing
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/grace"

# We use the sync engine from app.db
engine = get_engine(DATABASE_URL)

def get_db():
    """Synchronous database session generator."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

def get_pool_status():
    """Utility for system startup health checks."""
    try:
        return engine.pool.status()
    except Exception:
        return "Uninitialized"