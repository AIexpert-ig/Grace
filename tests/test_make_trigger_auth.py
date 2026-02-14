import hashlib
import hmac
import json
import time

import pytest

from app import main as app_main


def _sign(secret: str, timestamp: str, raw_body: bytes) -> str:
    message = timestamp.encode() + b"." + raw_body
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


@pytest.mark.asyncio
async def test_make_trigger_requires_admin_token(monkeypatch, test_client):
    monkeypatch.setenv("ADMIN_TOKEN", "admin-token")
    monkeypatch.setenv("MAKE_WEBHOOK_URL", "https://example.com/webhook")
    monkeypatch.setenv("MAKE_SIGNING_SECRET", "")

    class FakeClient:
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            return False
        async def post(self, *_args, **_kwargs):
            class Resp:
                status_code = 200
            return Resp()

    monkeypatch.setattr(app_main, "_get_httpx_client", lambda: FakeClient())

    res = await test_client.post("/integrations/make/trigger", json={"version": "v1"})
    assert res.status_code == 401
    assert res.json()["required_header"] == "X-Admin-Token"


@pytest.mark.asyncio
async def test_make_trigger_admin_token_ok(monkeypatch, test_client):
    monkeypatch.setenv("ADMIN_TOKEN", "admin-token")
    monkeypatch.setenv("MAKE_WEBHOOK_URL", "https://example.com/webhook")

    class FakeClient:
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            return False
        async def post(self, *_args, **_kwargs):
            class Resp:
                status_code = 200
            return Resp()

    monkeypatch.setattr(app_main, "_get_httpx_client", lambda: FakeClient())

    res = await test_client.post(
        "/integrations/make/trigger",
        json={"version": "v1", "correlation_id": "c1"},
        headers={"X-Admin-Token": "admin-token"},
    )
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_make_trigger_hmac_ok(monkeypatch, test_client):
    monkeypatch.setenv("MAKE_SIGNING_SECRET", "secret")
    monkeypatch.setenv("MAKE_WEBHOOK_URL", "https://example.com/webhook")

    class FakeClient:
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            return False
        async def post(self, *_args, **_kwargs):
            class Resp:
                status_code = 200
            return Resp()

    monkeypatch.setattr(app_main, "_get_httpx_client", lambda: FakeClient())

    payload = {"version": "v1", "correlation_id": "c2"}
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    timestamp = str(int(time.time()))
    signature = _sign("secret", timestamp, body)

    res = await test_client.post(
        "/integrations/make/trigger",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Signature-Timestamp": timestamp,
            "X-Signature": signature,
        },
    )
    assert res.status_code == 200
