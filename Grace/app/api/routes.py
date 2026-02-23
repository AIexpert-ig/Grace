"""Minimal dashboard API endpoints (Phase 1: in-memory stores).

These endpoints exist to prevent 404s for the vanilla dashboard while the DB layer
is being finalized. Replace the in-memory getters with real persistence later.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

router = APIRouter()

# Phase 1: in-memory stores (empty by default).
_TICKETS: list[dict[str, Any]] = []
_EVENTS: list[dict[str, Any]] = []
_CALLS: list[dict[str, Any]] = []
_STAFF: list[dict[str, Any]] = []


def _clamp_limit(value: int, *, default: int, maximum: int) -> int:
    try:
        v = int(value)
    except Exception:
        return default
    if v < 1:
        return default
    return min(v, maximum)


def list_tickets(limit: int) -> list[dict[str, Any]]:
    return _TICKETS[:limit]


def list_events(limit: int) -> list[dict[str, Any]]:
    return _EVENTS[:limit]


def list_calls(limit: int) -> list[dict[str, Any]]:
    return _CALLS[:limit]


def list_staff(limit: int) -> list[dict[str, Any]]:
    return _STAFF[:limit]


@router.get("/tickets")
def get_tickets(limit: int = Query(50)) -> list[dict[str, Any]]:
    """Return recent tickets."""
    try:
        safe_limit = _clamp_limit(limit, default=50, maximum=200)
        return list_tickets(safe_limit)
    except Exception:
        return []


@router.get("/events")
def get_events(limit: int = Query(100)) -> list[dict[str, Any]]:
    """Return recent events."""
    try:
        safe_limit = _clamp_limit(limit, default=100, maximum=500)
        return list_events(safe_limit)
    except Exception:
        return []


@router.get("/calls")
def get_calls(limit: int = Query(50)) -> list[dict[str, Any]]:
    """Return recent calls."""
    try:
        safe_limit = _clamp_limit(limit, default=50, maximum=200)
        return list_calls(safe_limit)
    except Exception:
        return []


@router.get("/staff")
def get_staff(limit: int = Query(100)) -> list[dict[str, Any]]:
    """Return staff directory entries."""
    try:
        safe_limit = _clamp_limit(limit, default=100, maximum=500)
        return list_staff(safe_limit)
    except Exception:
        return []

