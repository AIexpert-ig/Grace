import hashlib
import json
import time
import uuid
from collections import deque
from dataclasses import asdict

import httpx

from app.core.config import settings
from app.core.events import EventEnvelope, logger

_event_log: deque[EventEnvelope] = deque(maxlen=100)


def _parse_admin_ids() -> set[int]:
    admins: set[int] = set()
    for part in settings.TELEGRAM_ADMIN_IDS.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            admins.add(int(part))
        except ValueError:
            continue
    return admins


def _is_admin(user_id: int) -> bool:
    return user_id in _parse_admin_ids()


def record_event(envelope: EventEnvelope) -> None:
    if not settings.ENABLE_TELEGRAM:
        return
    _event_log.append(envelope)


def get_last_events(limit: int = 10) -> list[dict]:
    return [asdict(evt) for evt in list(_event_log)[-limit:]]


async def send_message(chat_id: int | str, text: str) -> bool:
    """Send a message to a Telegram chat. Returns True on success."""
    token = (settings.TELEGRAM_BOT_TOKEN or "").strip()
    if not token or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                url,
                json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
            )
            return r.status_code == 200
    except Exception:
        return False


async def handle_command(text: str, user_id: int, bus) -> dict:
    command = text.strip()
    if command.startswith("/status"):
        return {"status": "ok", "message": "Grace online"}

    if command.startswith("/last"):
        if not _is_admin(user_id):
            return {"error": "unauthorized"}
        return {"status": "ok", "events": get_last_events(10)}

    if command.startswith("/escalate"):
        if not _is_admin(user_id):
            return {"error": "unauthorized"}

        raw_payload = command[len("/escalate") :].strip()
        if not raw_payload:
            return {"error": "invalid_json"}
        try:
            payload = json.loads(raw_payload)
        except json.JSONDecodeError:
            return {"error": "invalid_json"}

        idempotency_key = hashlib.sha256(raw_payload.encode("utf-8")).hexdigest()
        envelope = EventEnvelope(
            version="v1",
            source="telegram",
            type="escalation.create",
            idempotency_key=idempotency_key,
            timestamp=int(time.time()),
            correlation_id=str(uuid.uuid4()),
            payload=payload,
        )

        await bus.publish(envelope)
        record_event(envelope)
        return {"status": "accepted", "correlation_id": envelope.correlation_id}

    return {"status": "ignored"}


async def handle_ticket_created(payload: dict, correlation_id: str) -> None:
    if not settings.ENABLE_TELEGRAM:
        return

    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
        logger.warning(
            "Telegram enabled but credentials missing",
            extra={"correlation_id": correlation_id},
        )
        return

    message = (
        "🚨 **ESCALATION ALERT**\n"
        f"Guest: {payload.get('guest_name', 'Unknown')}\n"
        f"Room: {payload.get('room_number', 'N/A')}\n"
        f"Issue: {payload.get('issue', 'No details')}\n"
        f"ID: `{correlation_id}`"
    )

    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                url,
                json={
                    "chat_id": settings.TELEGRAM_CHAT_ID,
                    "text": message,
                    "parse_mode": "Markdown",
                },
            )
        logger.info("Telegram notification sent", extra={"correlation_id": correlation_id})
    except Exception as exc:  # pragma: no cover - network dependent
        logger.error(
            "Telegram send failed: %s",
            exc,
            extra={"correlation_id": correlation_id},
        )
