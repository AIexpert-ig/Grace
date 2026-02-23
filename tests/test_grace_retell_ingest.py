from __future__ import annotations

from datetime import datetime

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from Grace.app import retell_ingest
from Grace.app.api import routes as dashboard_routes
from Grace.app.db import CallAnalysis, CallSession, Escalation, bootstrap_tables, get_engine, get_sessionmaker


def _session_factory(tmp_path):
    db_path = tmp_path / "grace_retell_test.db"
    engine = get_engine(f"sqlite:///{db_path}")
    bootstrap_tables(engine=engine)
    return get_sessionmaker(engine=engine)


def test_retell_ingest_call_started_persists_call(tmp_path):
    SessionLocal = _session_factory(tmp_path)

    res = retell_ingest.ingest_retell_webhook(
        {"call_id": "call-start-1", "from": "+15550001111"},
        event_type="call_started",
        correlation_id="corr-1",
        session_factory=SessionLocal,
    )
    assert res["ok"] is True

    db = SessionLocal()
    try:
        row = db.query(CallSession).filter(CallSession.id == "call-start-1").first()
        assert row is not None
        assert row.status == "Active"
        assert row.from_contact == "+15550001111"
    finally:
        db.close()


def test_retell_ingest_call_ended_updates_status(tmp_path):
    SessionLocal = _session_factory(tmp_path)

    retell_ingest.ingest_retell_webhook(
        {"call_id": "call-end-1"},
        event_type="call_started",
        correlation_id="corr-2",
        session_factory=SessionLocal,
    )
    retell_ingest.ingest_retell_webhook(
        {"call_id": "call-end-1"},
        event_type="call_ended",
        correlation_id="corr-3",
        session_factory=SessionLocal,
    )

    db = SessionLocal()
    try:
        row = db.query(CallSession).filter(CallSession.id == "call-end-1").first()
        assert row is not None
        assert row.status == "Ended"
    finally:
        db.close()


def test_retell_ingest_call_analyzed_creates_ticket_idempotent(tmp_path):
    SessionLocal = _session_factory(tmp_path)

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

    first = retell_ingest.ingest_retell_webhook(
        payload,
        event_type="call_analyzed",
        correlation_id="corr-a1",
        session_factory=SessionLocal,
    )
    second = retell_ingest.ingest_retell_webhook(
        payload,
        event_type="call_analyzed",
        correlation_id="corr-a2",
        session_factory=SessionLocal,
    )

    assert first["ok"] is True
    assert second["ok"] is True
    assert first["ticket_id"] is not None
    assert second["ticket_id"] == first["ticket_id"]

    db = SessionLocal()
    try:
        tickets = db.query(Escalation).all()
        assert len(tickets) == 1
        assert "TRANSCRIPT" in (tickets[0].issue or "")

        analysis = db.query(CallAnalysis).filter(CallAnalysis.call_id == "call-analyzed-1").first()
        assert analysis is not None
        assert analysis.ticket_id == first["ticket_id"]
        assert analysis.summary
        assert analysis.transcript
    finally:
        db.close()


@pytest.mark.asyncio
async def test_api_calls_reads_db(monkeypatch, tmp_path):
    SessionLocal = _session_factory(tmp_path)

    db = SessionLocal()
    try:
        db.add(
            CallSession(
                id="call-api-1",
                from_contact="+19998887777",
                status="Active",
                intent="",
                latency_ms=None,
                started_at=datetime.utcnow(),
                transcript_snippet="Hello",
            )
        )
        db.commit()
    finally:
        db.close()

    monkeypatch.setattr(dashboard_routes, "SessionLocal", SessionLocal, raising=True)

    app = FastAPI()
    app.include_router(dashboard_routes.router, prefix="/api")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/calls", params={"limit": 10})

    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert any(item.get("id") == "call-api-1" for item in data)

