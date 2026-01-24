"""Tests for the call webhook endpoint."""
import hashlib
import hmac
import json
import time
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.core.config import settings


def build_webhook_headers(body: dict, api_key: str | None = None) -> tuple[dict[str, str], str]:
    """Build signed webhook headers and JSON body for tests."""
    timestamp = int(time.time())
    body_json = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
    message = f"{timestamp}{body_json}"
    signature = hmac.new(
        settings.HMAC_SECRET.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    headers = {
        "X-Signature": signature,
        "X-Timestamp": str(timestamp),
        "Content-Type": "application/json",
    }
    if api_key is not None:
        headers["X-API-Key"] = api_key

    return headers, body_json


@pytest.mark.asyncio
async def test_post_call_webhook_high_urgency():
    """Test webhook processing for high urgency calls."""
    with patch("app.main.telegram_service.send_alert", new_callable=AsyncMock) as mock_send_alert:
        body = {
            "caller_name": "John Doe",
            "room_number": "101",
            "callback_number": "+123456789",
            "summary": "Guest is unhappy",
            "urgency": "high"
        }
        headers, body_json = build_webhook_headers(body, settings.API_KEY)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post(
                "/post-call-webhook",
                content=body_json,
                headers=headers
            )

        assert response.status_code == 200
        mock_send_alert.assert_called_once()
        assert "John Doe" in mock_send_alert.call_args[0][0]


@pytest.mark.asyncio
async def test_post_call_webhook_low_urgency():
    """Test webhook processing for low urgency calls."""
    with patch("app.main.telegram_service.send_alert", new_callable=AsyncMock) as mock_send_alert:
        body = {
            "caller_name": "Jane Doe",
            "room_number": "102",
            "callback_number": "+987654321",
            "summary": "Just asking about breakfast",
            "urgency": "low"
        }
        headers, body_json = build_webhook_headers(body, settings.API_KEY)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post(
                "/post-call-webhook",
                content=body_json,
                headers=headers
            )

        assert response.status_code == 200
        mock_send_alert.assert_not_called()


@pytest.mark.asyncio
async def test_post_call_webhook_invalid_api_key():
    """Test webhook with invalid API key."""
    with patch("app.main.telegram_service.send_alert", new_callable=AsyncMock) as mock_send_alert:
        body = {
            "caller_name": "John Doe",
            "room_number": "101",
            "callback_number": "+123456789",
            "summary": "Test",
            "urgency": "high"
        }
        headers, body_json = build_webhook_headers(body, "invalid_key")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post(
                "/post-call-webhook",
                content=body_json,
                headers=headers
            )

    assert response.status_code == 401
    assert "Invalid API Key" in response.json()["detail"]
    mock_send_alert.assert_not_called()
