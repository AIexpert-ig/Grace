"""Database models + session for the Railway (Grace/) FastAPI app.

This module is intentionally small and sync-SQLAlchemy-only so it can be reused by:
- the dashboard API router (/api/*)
- Retell webhook ingestion (persist calls + create tickets)

Phase 1 uses table bootstrapping via `create_all` (no migrations).
"""

from __future__ import annotations

import logging
from datetime import datetime
from functools import lru_cache
from typing import Any

from sqlalchemy import Column, DateTime, Integer, String, Text, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, sessionmaker

from .core.config import settings

Base = declarative_base()


class Escalation(Base):
    __tablename__ = "escalations"

    id = Column(Integer, primary_key=True, index=True)
    guest_name = Column(String, default="Unknown Guest")
    room_number = Column(String, default="Unknown")
    issue = Column(Text)
    status = Column(String, default="OPEN")
    sentiment = Column(String, default="Neutral")
    created_at = Column(DateTime, default=datetime.utcnow)


class CallSession(Base):
    __tablename__ = "call_sessions"

    id = Column(String, primary_key=True, index=True)
    from_contact = Column(String, default="")
    status = Column(String, default="Active")
    intent = Column(String, default="")
    latency_ms = Column(Integer, nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow, index=True)
    transcript_snippet = Column(Text, default="")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CallAnalysis(Base):
    __tablename__ = "call_analyses"

    call_id = Column(String, primary_key=True, index=True)
    caller_name = Column(String, default="")
    intent = Column(String, default="")
    requested_service = Column(String, default="")
    selected_time = Column(String, default="")
    outcome = Column(String, default="")
    summary = Column(Text, default="")
    transcript = Column(Text, default="")
    ticket_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


def _sync_database_url() -> str:
    return settings.DATABASE_URL_SYNC


@lru_cache(maxsize=8)
def get_engine(database_url: str | None = None) -> Engine:
    url = (database_url or _sync_database_url()).strip()
    return create_engine(url, pool_pre_ping=True)


def get_sessionmaker(*, engine: Engine | None = None) -> sessionmaker:
    bind = engine or get_engine()
    return sessionmaker(autocommit=False, autoflush=False, bind=bind)


SessionLocal = get_sessionmaker()


def bootstrap_tables(*, engine: Engine | None = None) -> None:
    bind = engine or get_engine()
    try:
        Base.metadata.create_all(
            bind=bind,
            tables=[
                Escalation.__table__,
                CallSession.__table__,
                CallAnalysis.__table__,
            ],
        )
    except Exception as exc:  # pragma: no cover - defensive
        logging.getLogger("db").warning("grace_table_bootstrap_failed: %s", exc)


def safe_close(session: Any) -> None:
    try:
        session.close()
    except Exception:
        pass

