from sqlalchemy.ext.asyncio import create_asyncio_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
import os

DATABASE_URL = os.getenv("DATABASE_PUBLIC_URL", "").replace("postgresql://", "postgresql+asyncpg://")

engine = create_asyncio_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()

# This is the function main.py is looking for
def get_engine():
    return engine

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
