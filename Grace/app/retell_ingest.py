"""Retell webhook ingestion -> persist calls + ticket creation (idempotent).

This is intentionally framework-agnostic (no FastAPI dependencies) so it can be:
- called from the `/webhook` handler
- tested in isolation
"""

from __future__ import annotations

import logging
from datetime import datetime
import re
from typing import Any

from sqlalchemy.exc import IntegrityError

from .db import CallAnalysis, CallSession, Escalation, SessionLocal, safe_close

_log = logging.getLogger("retell.ingest")


def _first_str(mapping: dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        value = mapping.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _extract_call_id(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    call_id = _first_str(payload, ["call_id", "callId", "conversation_id", "conversationId", "id"])
    if call_id:
        return call_id
    call_obj = payload.get("call")
    if isinstance(call_obj, dict):
        return _first_str(call_obj, ["call_id", "callId", "id"])
    return ""


def _normalize_event_type(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    lowered = raw.lower()
    normalized = re.sub(r"[^a-z0-9]+", "_", lowered).strip("_")
    for token in ("call_started", "call_ended", "call_analyzed"):
        if token in normalized:
            return token
    return normalized


def _transcript_to_text(transcript: Any) -> str:
    if isinstance(transcript, str):
        return transcript.strip()
    if not isinstance(transcript, list):
        return ""
    lines: list[str] = []
    for item in transcript:
        if not isinstance(item, dict):
            continue
        role = item.get("role") or item.get("speaker") or item.get("type") or ""
        content = item.get("content") or item.get("text") or item.get("message") or ""
        if not isinstance(content, str) or not content.strip():
            continue
        prefix = str(role).strip().title() if role else "Line"
        lines.append(f"{prefix}: {content.strip()}")
    return "\n".join(lines).strip()


def _derive_snippet(text: str, *, max_len: int = 280) -> str:
    cleaned = (text or "").strip()
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 1] + "…"


def _extract_analysis(payload: dict[str, Any]) -> dict[str, Any]:
    analysis = payload.get("analysis")
    if isinstance(analysis, dict):
        return analysis
    analysis = payload.get("call_analysis")
    if isinstance(analysis, dict):
        return analysis
    analysis = payload.get("callAnalysis")
    if isinstance(analysis, dict):
        return analysis
    return {}


def _build_ticket_issue(
    *,
    call_id: str,
    caller_name: str,
    intent: str,
    requested_service: str,
    selected_time: str,
    outcome: str,
    summary: str,
    transcript_text: str,
) -> str:
    parts: list[str] = []
    parts.append(f"call_id={call_id}")
    if caller_name:
        parts.append(f"caller_name={caller_name}")
    if intent:
        parts.append(f"intent={intent}")
    if requested_service:
        parts.append(f"requested_service={requested_service}")
    if selected_time:
        parts.append(f"selected_time={selected_time}")
    if outcome:
        parts.append(f"outcome={outcome}")

    header = " | ".join(parts)
    body = summary.strip() if summary else ""
    transcript_block = transcript_text.strip() if transcript_text else ""
    if transcript_block:
        transcript_block = f"\n\n---\nTRANSCRIPT\n{transcript_block}"

    if body:
        return f"{header}\n\nSUMMARY\n{body}{transcript_block}".strip()
    if transcript_block:
        return f"{header}{transcript_block}".strip()
    return header.strip()


def ingest_retell_webhook(
    payload: Any,
    *,
    event_type: str,
    correlation_id: str,
    session_factory=SessionLocal,
) -> dict[str, Any]:
    """Persist Retell call updates and (on analyzed) create a ticket exactly once."""

    normalized_type = _normalize_event_type(event_type)
    call_id = _extract_call_id(payload)
    if not call_id:
        _log.warning(
            "RETELL_INGEST_SKIP missing_call_id event_type=%s correlation_id=%s",
            normalized_type or event_type,
            correlation_id,
        )
        return {"ok": False, "reason": "missing_call_id"}

    if not isinstance(payload, dict):
        payload = {"call_id": call_id}

    now = datetime.utcnow()
    from_contact = _first_str(payload, ["from", "from_number", "fromNumber", "from_contact", "caller"])

    intent = _first_str(payload, ["intent", "call_intent", "callIntent"])
    try:
        latency_ms = int(payload.get("latency_ms")) if payload.get("latency_ms") is not None else None
    except Exception:
        latency_ms = None

    transcript_text = _transcript_to_text(payload.get("transcript"))
    snippet = _derive_snippet(transcript_text)

    db = session_factory()
    try:
        session = db.query(CallSession).filter(CallSession.id == call_id).first()
        if not session:
            status = "Active"
            if normalized_type == "call_ended":
                status = "Ended"
            elif normalized_type == "call_analyzed":
                status = "Analyzed"
            session = CallSession(
                id=call_id,
                from_contact=from_contact or "",
                status=status,
                intent=intent or "",
                latency_ms=latency_ms,
                started_at=now,
                transcript_snippet=snippet or "",
                updated_at=now,
            )
            db.add(session)
        else:
            if from_contact:
                session.from_contact = from_contact
            if intent:
                session.intent = intent
            if latency_ms is not None:
                session.latency_ms = latency_ms
            if snippet:
                session.transcript_snippet = snippet
            if normalized_type == "call_started":
                session.status = "Active"
            elif normalized_type == "call_ended":
                session.status = "Ended"
            elif normalized_type == "call_analyzed":
                session.status = "Analyzed"

        ticket_id: int | None = None

        if normalized_type == "call_analyzed":
            analysis = _extract_analysis(payload)
            summary = _first_str(payload, ["summary", "call_summary", "callSummary"]) or _first_str(analysis, ["summary", "call_summary", "callSummary"])
            transcript_text = transcript_text or _transcript_to_text(analysis.get("transcript"))
            snippet = snippet or _derive_snippet(transcript_text)
            if snippet:
                session.transcript_snippet = snippet

            caller_name = _first_str(payload, ["caller_name", "callerName", "name"]) or _first_str(analysis, ["caller_name", "callerName", "name"])
            intent = intent or _first_str(analysis, ["intent", "call_intent", "callIntent"])
            requested_service = _first_str(analysis, ["requested_service", "requestedService", "service", "service_type"]) or _first_str(
                payload, ["requested_service", "requestedService", "service", "service_type"]
            )
            selected_time = _first_str(analysis, ["selected_time", "selectedTime", "time", "datetime", "date_time"]) or _first_str(
                payload, ["selected_time", "selectedTime", "time", "datetime", "date_time"]
            )
            outcome = _first_str(analysis, ["outcome", "call_outcome", "callOutcome", "result"]) or _first_str(payload, ["outcome", "result"])

            existing = db.query(CallAnalysis).filter(CallAnalysis.call_id == call_id).first()
            if existing and existing.ticket_id:
                ticket_id = int(existing.ticket_id)
                existing.summary = summary or existing.summary
                existing.transcript = transcript_text or existing.transcript
                existing.caller_name = caller_name or existing.caller_name
                existing.intent = intent or existing.intent
                existing.requested_service = requested_service or existing.requested_service
                existing.selected_time = selected_time or existing.selected_time
                existing.outcome = outcome or existing.outcome
            else:
                if not existing:
                    existing = CallAnalysis(
                        call_id=call_id,
                        caller_name=caller_name or "",
                        intent=intent or "",
                        requested_service=requested_service or "",
                        selected_time=selected_time or "",
                        outcome=outcome or "",
                        summary=summary or "",
                        transcript=transcript_text or "",
                        created_at=now,
                        updated_at=now,
                    )
                    db.add(existing)
                    db.flush()
                else:
                    existing.summary = summary or existing.summary
                    existing.transcript = transcript_text or existing.transcript
                    existing.caller_name = caller_name or existing.caller_name
                    existing.intent = intent or existing.intent
                    existing.requested_service = requested_service or existing.requested_service
                    existing.selected_time = selected_time or existing.selected_time
                    existing.outcome = outcome or existing.outcome

                issue = _build_ticket_issue(
                    call_id=call_id,
                    caller_name=caller_name,
                    intent=intent,
                    requested_service=requested_service,
                    selected_time=selected_time,
                    outcome=outcome,
                    summary=summary,
                    transcript_text=transcript_text,
                )

                ticket = Escalation(
                    guest_name=caller_name or "Unknown Caller",
                    room_number="N/A",
                    issue=issue,
                    status="OPEN",
                    sentiment="Neutral",
                    created_at=now,
                )
                db.add(ticket)
                db.flush()
                ticket_id = int(ticket.id)
                existing.ticket_id = ticket_id

                _log.info(
                    "RETELL_TICKET_CREATE_OK call_id=%s ticket_id=%s correlation_id=%s",
                    call_id,
                    ticket_id,
                    correlation_id,
                )

        db.commit()
        _log.info(
            "RETELL_DB_WRITE_OK event_type=%s call_id=%s ticket_id=%s correlation_id=%s",
            normalized_type or event_type,
            call_id,
            ticket_id,
            correlation_id,
        )
        return {"ok": True, "call_id": call_id, "ticket_id": ticket_id}
    except IntegrityError:
        db.rollback()
        _log.info(
            "RETELL_TICKET_CREATE_DUP call_id=%s correlation_id=%s",
            call_id,
            correlation_id,
        )
        try:
            analysis = db.query(CallAnalysis).filter(CallAnalysis.call_id == call_id).first()
            db.commit()
            return {"ok": True, "call_id": call_id, "ticket_id": int(analysis.ticket_id) if analysis and analysis.ticket_id else None}
        except Exception as exc:
            _log.warning(
                "RETELL_DB_WRITE_FAILED after_dedup event_type=%s call_id=%s correlation_id=%s err=%s",
                normalized_type or event_type,
                call_id,
                correlation_id,
                exc,
            )
            return {"ok": False, "reason": "db_error"}
    except Exception as exc:
        db.rollback()
        if normalized_type == "call_analyzed":
            _log.warning(
                "RETELL_TICKET_CREATE_FAILED call_id=%s correlation_id=%s err=%s",
                call_id,
                correlation_id,
                exc,
            )
        _log.warning(
            "RETELL_DB_WRITE_FAILED event_type=%s call_id=%s correlation_id=%s err=%s",
            normalized_type or event_type,
            call_id,
            correlation_id,
            exc,
        )
        return {"ok": False, "reason": "db_error"}
    finally:
        safe_close(db)
