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


@pytest.mark.asyncio
async def test_webhook_missing_secret_returns_503(monkeypatch, test_client):
    _set_setting(monkeypatch, "RETELL_SIGNING_SECRET", None)

    payload = {"event": "call"}
    body = json.dumps(payload).encode("utf-8")

    res = await test_client.post("/webhook", content=body, headers={"Content-Type": "application/json"})

    assert res.status_code == 503
    assert res.json()["error"] == "retell_signing_secret_missing"


@pytest.mark.asyncio
async def test_webhook_invalid_signature_returns_401(monkeypatch, test_client):
    _set_setting(monkeypatch, "RETELL_SIGNING_SECRET", "secret")

    payload = {"event": "call"}
    body = json.dumps(payload).encode("utf-8")
    timestamp = str(int(time.time()))

    res_missing = await test_client.post(
        "/webhook",
        content=body,
        headers={"Content-Type": "application/json"},
    )
    assert res_missing.status_code == 401
    assert res_missing.json()["error"] == "missing_signature_headers"

    res_invalid = await test_client.post(
        "/webhook",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Signature-Timestamp": timestamp,
            "X-Signature": "bad",
        },
    )
    assert res_invalid.status_code == 401
    assert res_invalid.json()["error"] == "signature_mismatch"


@pytest.mark.asyncio
async def test_webhook_expired_timestamp_returns_401(monkeypatch, test_client):
    _set_setting(monkeypatch, "RETELL_SIGNING_SECRET", "secret")
    _set_setting(monkeypatch, "WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS", 1)

    payload = {"event": "call"}
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    timestamp = str(int(time.time()) - 10)
    signature = _sign("secret", timestamp, body)

    res = await test_client.post(
        "/webhook",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Signature-Timestamp": timestamp,
            "X-Signature": signature,
        },
    )
    assert res.status_code == 401
    assert res.json()["error"] == "timestamp_invalid_or_expired"


@pytest.mark.asyncio
async def test_webhook_valid_signature_accepted_200(monkeypatch, test_client):
    _set_setting(monkeypatch, "RETELL_SIGNING_SECRET", "secret")

    payload = {"event": "call"}
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    timestamp = str(int(time.time()))
    signature = _sign("secret", timestamp, body)

    res = await test_client.post(
        "/webhook",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Signature-Timestamp": timestamp,
            "X-Signature": signature,
        },
    )

    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "accepted"
    assert "correlation_id" in data


@pytest.mark.asyncio
async def test_webhook_duplicate_idempotency_returns_duplicate(monkeypatch, test_client):
    _set_setting(monkeypatch, "RETELL_SIGNING_SECRET", "secret")

    payload = {"event": "call"}
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    timestamp = str(int(time.time()))
    signature = _sign("secret", timestamp, body)

    headers = {
        "Content-Type": "application/json",
        "X-Signature-Timestamp": timestamp,
        "X-Signature": signature,
    }

    first = await test_client.post("/webhook", content=body, headers=headers)
    second = await test_client.post("/webhook", content=body, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["status"] == "duplicate"


@pytest.mark.asyncio
async def test_webhook_invalid_json_returns_400(monkeypatch, test_client):
    _set_setting(monkeypatch, "RETELL_SIGNING_SECRET", "secret")

    body = b"not-json"
    timestamp = str(int(time.time()))
    signature = _sign("secret", timestamp, body)

    res = await test_client.post(
        "/webhook",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Signature-Timestamp": timestamp,
            "X-Signature": signature,
        },
    )

    assert res.status_code == 400
    assert res.json()["error"] == "invalid_json"
