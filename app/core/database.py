from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
import os

# Database URL adjustment for Async
DATABASE_URL = os.getenv("DATABASE_PUBLIC_URL", "").replace("postgresql://", "postgresql+asyncpg://")

# create_async_engine is the correct SQLAlchemy 2.0 function
engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()

def get_engine():
    return engine

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
