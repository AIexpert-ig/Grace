from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
import os

raw_url = os.getenv("DATABASE_URL") or os.getenv("DATABASE_PUBLIC_URL")

if not raw_url:
    DATABASE_URL = "postgresql+asyncpg://user:pass@localhost/grace_db"
else:
    DATABASE_URL = raw_url.replace("postgresql://", "postgresql+asyncpg://")

engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()

def get_engine():
    return engine

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

def get_pool_status():
    return engine.pool.status()
