import hashlib
import hmac
import json
import time

import pytest

from app.core.config import settings


def _set_setting(monkeypatch, name, value):
    monkeypatch.setitem(settings.__dict__, name, value)


def _sign(secret: str, timestamp: str, raw_body: bytes) -> str:
    message = timestamp.encode() + b"." + raw_body
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def _make_envelope(idempotency_key="idem-1", correlation_id="corr-1"):
    return {
        "version": "v1",
        "source": "make",
        "type": "ticket.created",
        "idempotency_key": idempotency_key,
        "timestamp": int(time.time()),
        "correlation_id": correlation_id,
        "payload": {"hello": "world"},
    }


@pytest.mark.asyncio
async def test_make_endpoints_flag_off_return_404(test_client, monkeypatch):
    _set_setting(monkeypatch, "ENABLE_MAKE_WEBHOOKS", False)

    res_in = await test_client.post("/webhooks/make/in", json={})
    res_trigger = await test_client.post("/integrations/make/trigger", json={})

    assert res_in.status_code == 404
    assert res_trigger.status_code == 404


@pytest.mark.asyncio
async def test_make_ingress_missing_secret_returns_503(test_client, monkeypatch):
    _set_setting(monkeypatch, "ENABLE_MAKE_WEBHOOKS", True)
    _set_setting(monkeypatch, "MAKE_SIGNING_SECRET", None)

    res = await test_client.post("/webhooks/make/in", json={})

    assert res.status_code == 503
    assert res.json()["error"] == "make_signing_secret_missing"


@pytest.mark.asyncio
async def test_make_ingress_signature_valid_invalid(monkeypatch, test_client):
    _set_setting(monkeypatch, "ENABLE_MAKE_WEBHOOKS", True)
    _set_setting(monkeypatch, "MAKE_SIGNING_SECRET", "secret")

    envelope = _make_envelope()
    body = json.dumps(envelope, separators=(",", ":")).encode("utf-8")
    timestamp = str(int(time.time()))
    signature = _sign("secret", timestamp, body)

    res_valid = await test_client.post(
        "/webhooks/make/in",
        content=body,
        headers={
            "X-Signature-Timestamp": timestamp,
            "X-Signature": signature,
            "Content-Type": "application/json",
        },
    )
    assert res_valid.status_code == 200
    assert res_valid.json()["status"] == "accepted"

    res_invalid = await test_client.post(
        "/webhooks/make/in",
        content=body,
        headers={
            "X-Signature-Timestamp": timestamp,
            "X-Signature": "invalid",
            "Content-Type": "application/json",
        },
    )
    assert res_invalid.status_code == 401
    assert "error" in res_invalid.json()


@pytest.mark.asyncio
async def test_make_ingress_schema_invalid_returns_400(monkeypatch, test_client):
    _set_setting(monkeypatch, "ENABLE_MAKE_WEBHOOKS", True)
    _set_setting(monkeypatch, "MAKE_SIGNING_SECRET", "secret")

    payload = {"version": "v2"}
    body = json.dumps(payload).encode("utf-8")
    timestamp = str(int(time.time()))
    signature = _sign("secret", timestamp, body)

    res = await test_client.post(
        "/webhooks/make/in",
        content=body,
        headers={
            "X-Signature-Timestamp": timestamp,
            "X-Signature": signature,
            "Content-Type": "application/json",
        },
    )

    assert res.status_code == 400
    assert res.json()["error"] == "invalid_envelope"


@pytest.mark.asyncio
async def test_make_ingress_duplicate_idempotency(monkeypatch, test_client):
    _set_setting(monkeypatch, "ENABLE_MAKE_WEBHOOKS", True)
    _set_setting(monkeypatch, "MAKE_SIGNING_SECRET", "secret")

    envelope = _make_envelope(idempotency_key="idem-dup", correlation_id="corr-dup")
    body = json.dumps(envelope, separators=(",", ":")).encode("utf-8")
    timestamp = str(int(time.time()))
    signature = _sign("secret", timestamp, body)

    headers = {
        "X-Signature-Timestamp": timestamp,
        "X-Signature": signature,
        "Content-Type": "application/json",
    }

    first = await test_client.post("/webhooks/make/in", content=body, headers=headers)
    second = await test_client.post("/webhooks/make/in", content=body, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["status"] == "duplicate"


@pytest.mark.asyncio
async def test_make_trigger_requires_admin_token(monkeypatch, test_client):
    _set_setting(monkeypatch, "ENABLE_MAKE_WEBHOOKS", True)
    _set_setting(monkeypatch, "ADMIN_TOKEN", "admin-token")
    _set_setting(monkeypatch, "MAKE_WEBHOOK_URL", "https://example.com/webhook")

    envelope = _make_envelope()

    res_missing = await test_client.post("/integrations/make/trigger", json=envelope)
    assert res_missing.status_code == 401
    assert res_missing.json()["error"] == "unauthorized"

    res_invalid = await test_client.post(
        "/integrations/make/trigger",
        json=envelope,
        headers={"X-Admin-Token": "wrong"},
    )
    assert res_invalid.status_code == 401


@pytest.mark.asyncio
async def test_make_trigger_admin_missing_token_config(monkeypatch, test_client):
    _set_setting(monkeypatch, "ENABLE_MAKE_WEBHOOKS", True)
    _set_setting(monkeypatch, "ADMIN_TOKEN", None)

    res = await test_client.post("/integrations/make/trigger", json=_make_envelope())
    assert res.status_code == 503
    assert res.json()["error"] == "admin_token_missing"


@pytest.mark.asyncio
async def test_make_trigger_outbound_mocked(monkeypatch, test_client):
    _set_setting(monkeypatch, "ENABLE_MAKE_WEBHOOKS", True)
    _set_setting(monkeypatch, "ADMIN_TOKEN", "admin-token")
    _set_setting(monkeypatch, "MAKE_WEBHOOK_URL", "https://example.com/webhook")

    calls = {}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, json=None, headers=None):
            calls["url"] = url
            calls["json"] = json
            calls["headers"] = headers
            class Dummy:
                status_code = 200
            return Dummy()

    monkeypatch.setattr(
        "app.services.make_integration.httpx.AsyncClient",
        FakeClient,
        raising=True,
    )

    envelope = _make_envelope(correlation_id="corr-send")

    res = await test_client.post(
        "/integrations/make/trigger",
        json=envelope,
        headers={"X-Admin-Token": "admin-token"},
    )

    assert res.status_code == 200
    assert res.json()["status"] == "sent"
    assert calls["headers"]["X-Correlation-Id"] == "corr-send"
