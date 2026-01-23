"""Database connection and session management with proper connection pooling."""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool, QueuePool
from sqlalchemy.orm import declarative_base

from .config import settings

# Determine pool class based on environment
# NullPool: For serverless (no connection pooling, new connection per request)
# QueuePool: For standard containers (connection pooling with limits)
pool_class = NullPool if settings.IS_SERVERLESS else QueuePool

# Create async engine with proper connection pooling
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,  # Set to True for SQL query logging
    future=True,
    poolclass=pool_class,
    pool_size=settings.DB_POOL_SIZE if not settings.IS_SERVERLESS else None,
    max_overflow=settings.DB_MAX_OVERFLOW if not settings.IS_SERVERLESS else None,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE,
    pool_pre_ping=settings.DB_POOL_PRE_PING,
    # Connection pool limits to prevent exhaustion
    connect_args={
        "server_settings": {
            "application_name": settings.PROJECT_NAME,
            "statement_timeout": "30000",  # 30 seconds query timeout
        }
    }
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

# Base class for models
Base = declarative_base()


async def get_db() -> AsyncSession:
    """Dependency to get database session from connection pool.
    
    Yields:
        AsyncSession: Database session that will be returned to the pool after use.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def get_pool_status() -> dict:
    """Get current connection pool status for monitoring.
    
    Returns:
        dict: Pool status information including size, checked out connections, etc.
    """
    pool = engine.pool
    if isinstance(pool, QueuePool):
        return {
            "pool_type": "QueuePool",
            "size": pool.size(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "checked_in": pool.checkedin(),
            "max_overflow": pool._max_overflow,
        }
    elif isinstance(pool, NullPool):
        return {
            "pool_type": "NullPool",
            "note": "No connection pooling (serverless mode)",
        }
    return {"pool_type": "Unknown"}
