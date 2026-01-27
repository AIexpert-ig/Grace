# app/core/database.py
import os
import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

# Imported to fix the previous NameError
from app.core.config import settings 

logger = logging.getLogger(__name__)

# RECOMMENDED: Use the environment variable provided by Railway
# If it's missing, it will fall back to your local test database
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    # Logic to ensure the asyncpg driver is used for asynchronous SQLAlchemy
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
    elif DATABASE_URL.startswith("postgresql://"):
        DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
else:
    # Fallback for local development or testing
    DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/grace"

# Connections calculated from your settings
CONNECTIONS_PER_WORKER = settings.DB_POOL_SIZE + settings.DB_MAX_OVERFLOW

# Initialize the Asynchronous Engine
engine = create_async_engine(
    DATABASE_URL, 
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_pre_ping=True,
    future=True
)

# Initialize the Asynchronous Session Factory
async_session_maker = async_sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

class Base(DeclarativeBase):
    pass

async def get_db():
    """Asynchronous database session generator."""
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()

def get_pool_status():
    """Utility for system startup health checks."""
    try:
        return engine.pool.status()
    except Exception:
        return "Uninitialized"