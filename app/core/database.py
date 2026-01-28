from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
import os

# Try DATABASE_URL first (Railway default), then DATABASE_PUBLIC_URL
raw_url = os.getenv("DATABASE_URL") or os.getenv("DATABASE_PUBLIC_URL")

if not raw_url:
    print("❌ ERROR: No Database URL found in environment variables!")
    # Use a dummy URL to prevent the parsing crash, though the app will still fail later
    DATABASE_URL = "postgresql+asyncpg://user:pass@localhost/dbname"
else:
    # SQLAlchemy Async requires the +asyncpg driver
    DATABASE_URL = raw_url.replace("postgresql://", "postgresql+asyncpg://")

engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()

def get_engine():
    return engine

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
