"""Pytest configuration and fixtures for integration tests."""
import asyncio
import os
from typing import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.core.database import Base, get_db
from app.main import app
from app.db_models import Rate

# Test database URL
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://test:test@localhost:5432/grace_test_db"
)

@pytest.fixture(scope="session")
def event_loop():
    """Create a modern instance of the event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
async def test_engine():
    """Create the async engine for the test database."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=NullPool,
        future=True
    )
    yield engine
    await engine.dispose()

@pytest.fixture(scope="session")
def session_maker(test_engine):
    """Create a session factory bound to the test engine."""
    return async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False
    )

@pytest.fixture(scope="function")
async def db_session(test_engine, session_maker) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session with automatic cleanup."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with session_maker() as session:
        yield session
        await session.rollback()
    
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture(scope="function")
async def test_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create a test client with database override."""
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    
    app.dependency_overrides.clear()

@pytest.fixture
async def sample_rate(db_session: AsyncSession) -> Rate:
    """Create a sample rate in the test database."""
    from datetime import datetime, timedelta
    
    rate = Rate(
        check_in_date=datetime.utcnow() + timedelta(days=5),
        check_out_date=datetime.utcnow() + timedelta(days=6),
        room_type="Standard",
        rate=500.0,
        currency="USD",
        is_available=True
    )
    db_session.add(rate)
    await db_session.commit()
    await db_session.refresh(rate)
    return rate