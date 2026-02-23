from __future__ import annotations

from fastapi import FastAPI
from starlette.testclient import TestClient

from app.api import routes as dashboard_routes
from app.db import Event, bootstrap_tables, get_engine, get_sessionmaker


def _session_factory(tmp_path):
    db_path = tmp_path / "events_api_test.db"
    engine = get_engine(f"sqlite:///{db_path}")
    bootstrap_tables(engine=engine)
    return get_sessionmaker(engine=engine)


def test_api_events_returns_rows(monkeypatch, tmp_path):
    SessionLocal = _session_factory(tmp_path)

    db = SessionLocal()
    try:
        db.add(
            Event(
                source="System",
                type="test_event",
                severity="low",
                text="local insert",
                payload={"ok": True},
            )
        )
        db.commit()
    finally:
        db.close()

    monkeypatch.setattr(dashboard_routes, "SessionLocal", SessionLocal, raising=True)

    app = FastAPI()
    app.include_router(dashboard_routes.router, prefix="/api")
    client = TestClient(app)

    res = client.get("/api/events?limit=10")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert any(item.get("type") == "test_event" and item.get("text") == "local insert" for item in data)

