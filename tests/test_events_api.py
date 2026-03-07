from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api import routes as dashboard_routes
from app.db import Base, Event


@pytest.fixture
async def events_app(tmp_path, monkeypatch):
    """Spin up a minimal FastAPI app backed by a throw-away SQLite database."""
    db_path = tmp_path / "events_api_test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Seed one event row so the endpoint has something to return
    async with factory() as db:
        db.add(
            Event(
                source="System",
                type="test_event",
                severity="low",
                text="local insert",
                payload={"ok": True},
            )
        )
        await db.commit()

    # Patch the module-level AsyncSessionLocal that the route handlers close over
    monkeypatch.setattr(dashboard_routes, "AsyncSessionLocal", factory)

    app = FastAPI()
    app.include_router(dashboard_routes.router, prefix="/api")

    yield app

    await engine.dispose()


async def test_api_events_returns_rows(events_app):
    async with AsyncClient(
        transport=ASGITransport(app=events_app), base_url="http://test"
    ) as client:
        res = await client.get("/api/events?limit=10")

    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert any(
        item.get("type") == "test_event" and item.get("text") == "local insert"
        for item in data
    ), f"Expected test_event row not found in response: {data}"
