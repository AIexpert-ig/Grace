"""Integration tests for webhook endpoint with HMAC signature validation."""
import hashlib
import hmac
import json
import time
from unittest.mock import AsyncMock, patch

import pytest
from app.core.config import settings


def build_signed_request(body: dict, timestamp: int) -> tuple[dict[str, str], str]:
    """Build signed webhook headers and JSON body for tests."""
    body_json = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
    message = f"{timestamp}{body_json}"
    signature = hmac.new(
        settings.HMAC_SECRET.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    headers = {
        "X-API-Key": settings.API_KEY,
        "X-Signature": signature,
        "X-Timestamp": str(timestamp),
        "Content-Type": "application/json",
    }
    return headers, body_json


@pytest.mark.asyncio
async def test_webhook_integration_high_urgency(test_client):
    """Integration test: Webhook with valid HMAC signature for high urgency."""
    body = {
        "caller_name": "John Doe",
        "room_number": "101",
        "callback_number": "+123456789",
        "summary": "Guest is unhappy",
        "urgency": "high"
    }
    timestamp = int(time.time())
    with patch("app.main.telegram_service.send_alert", new_callable=AsyncMock) as mock_send_alert:
        headers, body_json = build_signed_request(body, timestamp)
        response = await test_client.post(
            "/post-call-webhook",
            content=body_json,
            headers=headers
        )
    
    assert response.status_code == 200
    assert response.json()["status"] == "processed"
    mock_send_alert.assert_called_once()
    assert "John Doe" in mock_send_alert.call_args[0][0]


@pytest.mark.asyncio
async def test_webhook_integration_low_urgency(test_client):
    """Integration test: Webhook with valid HMAC signature for low urgency."""
    body = {
        "caller_name": "Jane Doe",
        "room_number": "102",
        "callback_number": "+987654321",
        "summary": "Just asking about breakfast",
        "urgency": "low"
    }
    timestamp = int(time.time())
    with patch("app.main.telegram_service.send_alert", new_callable=AsyncMock) as mock_send_alert:
        headers, body_json = build_signed_request(body, timestamp)
        response = await test_client.post(
            "/post-call-webhook",
            content=body_json,
            headers=headers
        )
    
    assert response.status_code == 200
    assert response.json()["status"] == "processed"
    mock_send_alert.assert_not_called()


@pytest.mark.asyncio
async def test_webhook_integration_invalid_signature(test_client):
    """Integration test: Webhook with invalid HMAC signature."""
    body = {
        "caller_name": "John Doe",
        "room_number": "101",
        "callback_number": "+123456789",
        "summary": "Test",
        "urgency": "high"
    }
    timestamp = int(time.time())
    
    headers, body_json = build_signed_request(body, timestamp)
    headers["X-Signature"] = "invalid_signature"
    response = await test_client.post(
        "/post-call-webhook",
        content=body_json,
        headers=headers
    )
    
    assert response.status_code == 401
    assert "Invalid HMAC signature" in response.json()["detail"]


@pytest.mark.asyncio
async def test_webhook_integration_missing_signature(test_client):
    """Integration test: Webhook without signature header."""
    body = {
        "caller_name": "John Doe",
        "room_number": "101",
        "callback_number": "+123456789",
        "summary": "Test",
        "urgency": "high"
    }
    
    timestamp = int(time.time())
    headers, body_json = build_signed_request(body, timestamp)
    headers.pop("X-Signature", None)
    response = await test_client.post(
        "/post-call-webhook",
        content=body_json,
        headers=headers
    )
    
    assert response.status_code == 401
    assert "Missing" in response.json()["detail"]


@pytest.mark.asyncio
async def test_webhook_integration_replay_attack(test_client):
    """Integration test: Reject old timestamp (replay attack prevention)."""
    body = {
        "caller_name": "John Doe",
        "room_number": "101",
        "callback_number": "+123456789",
        "summary": "Test",
        "urgency": "high"
    }
    # Use timestamp from 10 minutes ago
    old_timestamp = int(time.time()) - 600
    headers, body_json = build_signed_request(body, old_timestamp)
    response = await test_client.post(
        "/post-call-webhook",
        content=body_json,
        headers=headers
    )
    
    assert response.status_code == 401
    assert "too old" in response.json()["detail"].lower()
