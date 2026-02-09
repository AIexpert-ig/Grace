import asyncio
import time

import pytest

from app.core.events import EventBus, EventEnvelope


@pytest.mark.asyncio
async def test_event_envelope_validation_v1():
    envelope = EventEnvelope(
        version="v1",
        source="unit-test",
        type="ticket.created",
        idempotency_key="idem-1",
        timestamp=1234567890,
        correlation_id="corr-1",
        payload={"ok": True},
    )
    assert envelope.version == "v1"

    with pytest.raises(ValueError):
        EventEnvelope(
            version="v2",
            source="unit-test",
            type="ticket.created",
            idempotency_key="idem-1",
            timestamp=1234567890,
            correlation_id="corr-1",
            payload={"ok": True},
        )


@pytest.mark.asyncio
async def test_event_bus_idempotency_duplicate():
    bus = EventBus(ttl_seconds=3600)
    calls = []

    async def handler(envelope):
        calls.append(envelope.idempotency_key)

    bus.register_handler(event_type="ticket.created", handler=handler)

    envelope = EventEnvelope(
        version="v1",
        source="unit-test",
        type="ticket.created",
        idempotency_key="idem-dup",
        timestamp=1234567890,
        correlation_id="corr-dup",
        payload={"ok": True},
    )

    first = await bus.publish(envelope)
    second = await bus.publish(envelope)

    assert first.status == "processed"
    assert second.status == "duplicate"
    assert calls == ["idem-dup"]


@pytest.mark.asyncio
async def test_event_bus_ttl_expiry(monkeypatch):
    bus = EventBus(ttl_seconds=1)

    async def handler(_envelope):
        return None

    bus.register_handler(event_type="ticket.created", handler=handler)

    envelope = EventEnvelope(
        version="v1",
        source="unit-test",
        type="ticket.created",
        idempotency_key="idem-ttl",
        timestamp=1234567890,
        correlation_id="corr-ttl",
        payload={"ok": True},
    )

    monkeypatch.setattr(time, "time", lambda: 1000)
    first = await bus.publish(envelope)

    monkeypatch.setattr(time, "time", lambda: 1002)
    second = await bus.publish(envelope)

    assert first.status == "processed"
    assert second.status == "processed"


@pytest.mark.asyncio
async def test_event_bus_deadletter_capture(monkeypatch):
    bus = EventBus(ttl_seconds=3600)

    async def failing_handler(_envelope):
        raise RuntimeError("boom")

    bus.register_handler(event_type="ticket.created", handler=failing_handler)

    envelope = EventEnvelope(
        version="v1",
        source="unit-test",
        type="ticket.created",
        idempotency_key="idem-dead",
        timestamp=1234567890,
        correlation_id="corr-dead",
        payload={"ok": True},
    )

    async def noop_sleep(_):
        return None

    monkeypatch.setattr(asyncio, "sleep", noop_sleep)

    result = await bus.publish(envelope)

    deadletters = bus.get_deadletters()
    assert result.status == "failed"
    assert len(deadletters) == 1
    assert deadletters[0]["envelope"].idempotency_key == "idem-dead"
