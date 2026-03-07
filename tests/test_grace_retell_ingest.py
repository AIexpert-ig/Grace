"""Tests for Retell webhook ingestion (async version).

Verifies call_started / call_ended / call_analyzed persistence and
idempotent ticket creation against a throw-away SQLite database.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api import routes as dashboard_routes
from app.db import Base, CallAnalysis, CallSession, Escalation
from app.retell_ingest import ingest_retell_webhook


@pytest.fixture
async def retell_db(tmp_path):
    """Create a throw-away async SQLite engine + session factory."""
    db_path = tmp_path / "grace_retell_test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield factory
    await engine.dispose()


# ── call_started ──────────────────────────────────────────────────────────


async def test_retell_ingest_call_started_persists_call(retell_db):
    res = await ingest_retell_webhook(
        {"call_id": "call-start-1", "from": "+15550001111"},
        event_type="call_started",
        correlation_id="corr-1",
        session_factory=retell_db,
    )
    assert res["ok"] is True

    async with retell_db() as db:
        result = await db.execute(
            select(CallSession).where(CallSession.id == "call-start-1")
        )
        row = result.scalars().first()
        assert row is not None
        assert row.status == "Active"
        assert row.from_contact == "+15550001111"


# ── call_ended ────────────────────────────────────────────────────────────


async def test_retell_ingest_call_ended_updates_status(retell_db):
    await ingest_retell_webhook(
        {"call_id": "call-end-1"},
        event_type="call_started",
        correlation_id="corr-2",
        session_factory=retell_db,
    )
    await ingest_retell_webhook(
        {"call_id": "call-end-1"},
        event_type="call_ended",
        correlation_id="corr-3",
        session_factory=retell_db,
    )

    async with retell_db() as db:
        result = await db.execute(
            select(CallSession).where(CallSession.id == "call-end-1")
        )
        row = result.scalars().first()
        assert row is not None
        assert row.status == "Ended"


# ── call_analyzed (idempotent ticket) ─────────────────────────────────────


async def test_retell_ingest_call_analyzed_creates_ticket_idempotent(retell_db):
    payload = {
        "call_id": "call-analyzed-1",
        "analysis": {
            "summary": "Guest requested a Swedish massage.",
            "intent": "spa booking",
            "requested_service": "Swedish massage",
            "selected_time": "2026-02-23T18:30:00Z",
            "outcome": "booked_pending_confirmation",
            "caller_name": "John Doe",
        },
        "transcript": [
            {"role": "user", "content": "Hi, I'd like to book a Swedish massage for tonight."},
            {"role": "assistant", "content": "Sure — what time works best?"},
        ],
    }

    first = await ingest_retell_webhook(
        payload,
        event_type="call_analyzed",
        correlation_id="corr-a1",
        session_factory=retell_db,
    )
    second = await ingest_retell_webhook(
        payload,
        event_type="call_analyzed",
        correlation_id="corr-a2",
        session_factory=retell_db,
    )

    assert first["ok"] is True
    assert second["ok"] is True
    assert first["ticket_id"] is not None
    assert second["ticket_id"] == first["ticket_id"]

    async with retell_db() as db:
        ticket_result = await db.execute(select(Escalation))
        tickets = ticket_result.scalars().all()
        assert len(tickets) == 1
        assert "TRANSCRIPT" in (tickets[0].issue or "")

        analysis_result = await db.execute(
            select(CallAnalysis).where(CallAnalysis.call_id == "call-analyzed-1")
        )
        analysis = analysis_result.scalars().first()
        assert analysis is not None
        assert analysis.ticket_id == first["ticket_id"]
        assert analysis.summary
        assert analysis.transcript


# ── API /api/calls integration ────────────────────────────────────────────


async def test_api_calls_reads_db(retell_db, monkeypatch):
    async with retell_db() as db:
        db.add(
            CallSession(
                id="call-api-1",
                from_contact="+19998887777",
                status="Active",
                intent="",
                latency_ms=None,
                started_at=datetime.now(timezone.utc),
                transcript_snippet="Hello",
            )
        )
        await db.commit()

    monkeypatch.setattr(dashboard_routes, "AsyncSessionLocal", retell_db)

    app = FastAPI()
    app.include_router(dashboard_routes.router, prefix="/api")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        res = await client.get("/api/calls", params={"limit": 10})

    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert any(item.get("id") == "call-api-1" for item in data)
