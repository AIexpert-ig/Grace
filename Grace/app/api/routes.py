"""Dashboard API endpoints used by the vanilla JS dashboard."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Query

from ..db import CallSession, Escalation, SessionLocal, safe_close

router = APIRouter()

def _clamp_limit(value: int, *, default: int, maximum: int) -> int:
    try:
        v = int(value)
    except Exception:
        return default
    if v < 1:
        return default
    return min(v, maximum)


def _derive_severity(text_value: str | None) -> str:
    text_lower = (text_value or "").lower()
    if any(k in text_lower for k in ("leak", "fire", "smoke", "flood", "bleed", "emergency")):
        return "critical"
    if any(k in text_lower for k in ("refund", "cancel", "failed", "error", "charge", "angry", "complain")):
        return "high"
    if text_lower.strip():
        return "medium"
    return "low"


def _normalize_ticket_status(status_value: str | None) -> str:
    status_upper = (status_value or "").strip().upper()
    if status_upper in {"RESOLVED", "CLOSED", "DONE"}:
        return "Resolved"
    if status_upper in {"IN_PROGRESS", "IN PROGRESS"}:
        return "In Progress"
    return "Open"


@router.get("/tickets")
def get_tickets(limit: int = Query(50)) -> list[dict[str, Any]]:
    """Return recent tickets."""
    try:
        safe_limit = _clamp_limit(limit, default=50, maximum=200)
        db = SessionLocal()
        try:
            rows = db.query(Escalation).order_by(Escalation.created_at.desc()).limit(safe_limit).all()
            results: list[dict[str, Any]] = []
            for row in rows:
                created_at = row.created_at.isoformat() if isinstance(row.created_at, datetime) else None
                issue = row.issue or ""
                subject = issue.splitlines()[0].strip() if issue else ""
                if len(subject) > 140:
                    subject = subject[:139] + "…"
                results.append(
                    {
                        "id": f"TCK-{row.id}",
                        "customer": row.guest_name or "Unknown",
                        "source": "Voice" if "call_id=" in issue else "System",
                        "subject": subject or "Ticket",
                        "severity": _derive_severity(issue),
                        "status": _normalize_ticket_status(row.status),
                        "notes": issue,
                        "created_at": created_at,
                        "updated_at": created_at,
                    }
                )
            return results
        finally:
            safe_close(db)
    except Exception:
        return []


@router.get("/events")
def get_events(limit: int = Query(100)) -> list[dict[str, Any]]:
    """Return recent events."""
    try:
        _clamp_limit(limit, default=100, maximum=500)
        return []
    except Exception:
        return []


@router.get("/calls")
def get_calls(limit: int = Query(50)) -> list[dict[str, Any]]:
    """Return recent calls."""
    try:
        safe_limit = _clamp_limit(limit, default=50, maximum=200)
        db = SessionLocal()
        try:
            rows = db.query(CallSession).order_by(CallSession.started_at.desc()).limit(safe_limit).all()
            results: list[dict[str, Any]] = []
            for row in rows:
                started_at = row.started_at.isoformat() if isinstance(row.started_at, datetime) else None
                results.append(
                    {
                        "id": row.id,
                        "from": row.from_contact,
                        "status": row.status,
                        "intent": row.intent,
                        "latency_ms": row.latency_ms,
                        "started_at": started_at,
                        "transcript_snippet": row.transcript_snippet,
                    }
                )
            return results
        finally:
            safe_close(db)
    except Exception:
        return []


@router.get("/staff")
def get_staff(limit: int = Query(100)) -> list[dict[str, Any]]:
    """Return staff directory entries."""
    try:
        _clamp_limit(limit, default=100, maximum=500)
        return []
    except Exception:
        return []
