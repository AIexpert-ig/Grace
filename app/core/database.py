"""Database connection and session management with proper connection pooling."""
import warnings
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool, QueuePool
from sqlalchemy.orm import declarative_base

from .config import settings

# FIX: UPPER_CASE for module-level constants
CONNECTIONS_PER_WORKER = settings.DB_POOL_SIZE + settings.DB_MAX_OVERFLOW
TOTAL_CONNECTIONS = CONNECTIONS_PER_WORKER * settings.NUM_WORKERS

if not settings.IS_SERVERLESS and TOTAL_CONNECTIONS > settings.POSTGRES_MAX_CONNECTIONS * 0.8:
    warnings.warn(
        f"WARNING: Connection pool configuration may exhaust PostgreSQL connections!\n"
        f"  Total connections: {TOTAL_CONNECTIONS}\n"
        f"  PostgreSQL max_connections: {settings.POSTGRES_MAX_CONNECTIONS}",
        UserWarning
    )

# FIX: UPPER_CASE for module-level constants
POOL_CLASS = NullPool if settings.IS_SERVERLESS else QueuePool

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    poolclass=POOL_CLASS,
    pool_size=settings.DB_POOL_SIZE if not settings.IS_SERVERLESS else None,
    max_overflow=settings.DB_MAX_OVERFLOW if not settings.IS_SERVERLESS else None,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE,
    pool_pre_ping=settings.DB_POOL_PRE_PING,
    connect_args={
        "server_settings": {
            "application_name": settings.PROJECT_NAME,
            "statement_timeout": "30000",
        }
    }
)

# FIX: UPPER_CASE for module-level constants
ASYNC_SESSION_LOCAL = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

Base = declarative_base()

async def get_db() -> AsyncSession:
    """Dependency to get database session from connection pool."""
    async with ASYNC_SESSION_LOCAL() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

def get_pool_status() -> dict:
    """Get current connection pool status for monitoring."""
    pool = engine.pool
    if isinstance(pool, QueuePool):
        return {
            "pool_type": "QueuePool",
            "size": pool.size(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "checked_in": pool.checkedin(),
            # FIX: Tell Pylint to ignore protected access for this specific line
            "max_overflow": pool._max_overflow,  # pylint: disable=protected-access
        }
    # FIX: Removed unnecessary `elif` (R1705)
    if isinstance(pool, NullPool):
        return {
            "pool_type": "NullPool",
            "note": "No connection pooling (serverless mode)",
        }
    return {"pool_type": "Unknown"}