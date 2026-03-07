from dataclasses import asdict

import httpx

from app.core.config import settings
from app.core.events import EventEnvelope, logger


async def handle_make_trigger(payload: dict, correlation_id: str) -> None:
    if not settings.ENABLE_MAKE_WEBHOOKS:
        return

    if not settings.MAKE_WEBHOOK_URL:
        logger.warning(
            "Make.com enabled but URL missing",
            extra={"correlation_id": correlation_id},
        )
        return

    enriched_payload = {
        **payload,
        "correlation_id": correlation_id,
        "event_source": "grace_core",
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(settings.MAKE_WEBHOOK_URL, json=enriched_payload)
        logger.info("Make.com webhook triggered", extra={"correlation_id": correlation_id})
    except Exception as exc:  # pragma: no cover - network dependent
        logger.error(
            "Make.com trigger failed: %s",
            exc,
            extra={"correlation_id": correlation_id},
        )


async def send_make_webhook(url: str, envelope: EventEnvelope) -> httpx.Response:
    payload = asdict(envelope)
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            url,
            json=payload,
            headers={"X-Correlation-Id": envelope.correlation_id},
        )
    if response.status_code >= 400:
        raise RuntimeError("make_webhook_failed")
    return response
