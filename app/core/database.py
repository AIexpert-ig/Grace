from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
import os

user = os.getenv("POSTGRES_USER")
password = os.getenv("POSTGRES_PASSWORD")
host = os.getenv("PGHOST", "localhost")
port = os.getenv("PGPORT", "5432")
db = os.getenv("POSTGRES_DB")

if all([user, password, host, db]):
    DATABASE_URL = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db}"
else:
    raw_url = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost/grace_db")
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
