import hashlib
import hmac

import pytest

from app.core.config import settings


def _set_setting(monkeypatch, name, value):
    monkeypatch.setitem(settings.__dict__, name, value)


def _sign(secret: str, timestamp: str, raw_body: str) -> str:
    message = f"{timestamp}.{raw_body}".encode()
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


@pytest.mark.asyncio
async def test_retell_diagnose_disabled_in_production(monkeypatch, test_client):
    _set_setting(monkeypatch, "ENV", "production")
    _set_setting(monkeypatch, "ENABLE_DIAGNOSTIC_ENDPOINTS", False)
    _set_setting(monkeypatch, "ADMIN_TOKEN", "secret")

    res = await test_client.post("/webhooks/retell/diagnose", json={})
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_retell_diagnose_requires_admin_token(monkeypatch, test_client):
    _set_setting(monkeypatch, "ENV", "dev")
    _set_setting(monkeypatch, "ENABLE_DIAGNOSTIC_ENDPOINTS", False)
    _set_setting(monkeypatch, "ADMIN_TOKEN", "secret")

    res = await test_client.post("/webhooks/retell/diagnose", json={})
    assert res.status_code == 401
    assert res.json()["error"] == "unauthorized"


@pytest.mark.asyncio
async def test_retell_diagnose_returns_signature(monkeypatch, test_client):
    _set_setting(monkeypatch, "ENV", "dev")
    _set_setting(monkeypatch, "ENABLE_DIAGNOSTIC_ENDPOINTS", False)
    _set_setting(monkeypatch, "ADMIN_TOKEN", "secret")
    _set_setting(monkeypatch, "RETELL_SIGNING_SECRET", "sigsecret")

    payload = {
        "timestamp": "123",
        "raw_body": "{\"event\":\"test\"}",
    }

    res = await test_client.post(
        "/webhooks/retell/diagnose",
        json=payload,
        headers={"X-Admin-Token": "secret"},
    )

    assert res.status_code == 200
    data = res.json()
    assert data["signed_string"] == "123.{\"event\":\"test\"}"
    assert data["signature"] == _sign("sigsecret", "123", payload["raw_body"])
