"""Database models + async session for the Grace FastAPI app.

This module provides:
- SQLAlchemy ORM models (Escalation, CallSession, CallAnalysis, Event)
- An async engine backed by asyncpg
- An async session factory (AsyncSessionLocal)
- A FastAPI dependency (get_db) that yields an AsyncSession
- bootstrap_tables() to create tables on startup
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, AsyncGenerator

from sqlalchemy import Column, DateTime, Integer, String, Text, JSON, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func

from .core.config import settings

Base = declarative_base()


# ---------------------------------------------------------------------------
# ORM Models
# ---------------------------------------------------------------------------

class Escalation(Base):
    __tablename__ = "escalations"

    id = Column(Integer, primary_key=True, index=True)
    guest_name = Column(String, default="Unknown Guest")
    room_number = Column(String, default="Unknown")
    issue = Column(Text)
    status = Column(String, default="PENDING")
    sentiment = Column(String, default="Neutral")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    claimed_at = Column(DateTime(timezone=True), nullable=True)
    claimed_by = Column(String, nullable=True)


class CallSession(Base):
    __tablename__ = "call_sessions"

    id = Column(String, primary_key=True, index=True)
    from_contact = Column(String, default="")
    status = Column(String, default="Active")
    intent = Column(String, default="")
    latency_ms = Column(Integer, nullable=True)
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    transcript_snippet = Column(Text, default="")
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


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
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String, nullable=False, index=True)
    type = Column(String, nullable=False, index=True)
    severity = Column(String, nullable=False, default="low", server_default=text("'low'"))
    text = Column(Text, nullable=True)
    payload = Column(JSON, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )


# ---------------------------------------------------------------------------
# Async engine & session factory
# ---------------------------------------------------------------------------

def _build_engine_kwargs() -> dict:
    """Pool kwargs; pool_size/overflow are skipped for SQLite (test env)."""
    kwargs: dict = {"pool_pre_ping": settings.DB_POOL_PRE_PING}
    if not settings.DATABASE_URL.startswith("sqlite"):
        kwargs.update(
            {
                "pool_size": settings.DB_POOL_SIZE,
                "max_overflow": settings.DB_MAX_OVERFLOW,
                "pool_timeout": settings.DB_POOL_TIMEOUT,
                "pool_recycle": settings.DB_POOL_RECYCLE,
            }
        )
    return kwargs


async_engine = create_async_engine(settings.DATABASE_URL, **_build_engine_kwargs())

AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Backward-compat alias
SessionLocal = AsyncSessionLocal


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an AsyncSession; auto-closed on exit."""
    async with AsyncSessionLocal() as session:
        yield session


# ---------------------------------------------------------------------------
# Table bootstrap (called from lifespan)
# ---------------------------------------------------------------------------

async def bootstrap_tables() -> None:
    """Create all managed tables if they don't already exist."""
    from app.db_models import Rate  # local import avoids circular deps

    try:
        async with async_engine.begin() as conn:
            await conn.run_sync(
                Base.metadata.create_all,
                tables=[
                    Escalation.__table__,
                    CallSession.__table__,
                    CallAnalysis.__table__,
                    Event.__table__,
                    Rate.__table__,
                ],
            )
    except Exception as exc:
        logging.getLogger("db").warning("grace_table_bootstrap_failed: %s", exc)


# ---------------------------------------------------------------------------
# Compatibility shim
# ---------------------------------------------------------------------------

def safe_close(session: Any) -> None:
    """No-op: async sessions are closed by their context manager."""
