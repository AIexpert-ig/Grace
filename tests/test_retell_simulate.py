import hashlib
import json
import time
import uuid

import pytest

from app.core.config import settings
from app.core.events import EventBus, PublishResult


def _set_setting(monkeypatch, name, value):
    monkeypatch.setitem(settings.__dict__, name, value)


def _make_envelope(idempotency_key="idem-1", correlation_id="corr-1"):
    return {
        "version": "v1",
        "source": "retell",
        "type": "call_simulated",
        "idempotency_key": idempotency_key,
        "timestamp": int(time.time()),
        "correlation_id": correlation_id,
        "payload": {"ok": True},
    }


@pytest.mark.asyncio
async def test_retell_simulate_flag_off_returns_404(test_client, monkeypatch):
    _set_setting(monkeypatch, "ENABLE_RETELL_SIMULATION", False)

    res = await test_client.post("/webhooks/retell/simulate", json={})
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_retell_simulate_envelope_path_duplicate(monkeypatch, test_client):
    _set_setting(monkeypatch, "ENABLE_RETELL_SIMULATION", True)

    envelope = _make_envelope(idempotency_key="idem-dup", correlation_id="corr-dup")

    first = await test_client.post("/webhooks/retell/simulate", json=envelope)
    second = await test_client.post("/webhooks/retell/simulate", json=envelope)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["status"] == "duplicate"


@pytest.mark.asyncio
async def test_retell_simulate_wraps_retell_body(monkeypatch, test_client):
    _set_setting(monkeypatch, "ENABLE_RETELL_SIMULATION", True)

    captured = {}

    async def fake_publish(envelope):
        captured["envelope"] = envelope
        return PublishResult(status="processed", correlation_id=envelope.correlation_id, envelope=envelope)

    bus = EventBus()
    monkeypatch.setattr("app.main.bus", bus, raising=False)
    monkeypatch.setattr(bus, "publish", fake_publish, raising=True)

    body = {"call_id": str(uuid.uuid4()), "text": "hello"}
    raw = json.dumps(body, separators=(",", ":")).encode("utf-8")
    expected_idem = hashlib.sha256(raw).hexdigest()

    res = await test_client.post("/webhooks/retell/simulate", content=raw, headers={"Content-Type": "application/json"})
    assert res.status_code == 200

    envelope = captured["envelope"]
    assert envelope.version == "v1"
    assert envelope.source == "retell"
    assert envelope.type == "call_simulated"
    assert envelope.idempotency_key == expected_idem
    assert res.json()["correlation_id"] == envelope.correlation_id
