"""Integration tests for webhook endpoint with HMAC signature validation."""
import hashlib
import hmac
import json
import time
from unittest.mock import AsyncMock, patch

import pytest
from app.core.config import settings


def generate_hmac_signature(body: dict, timestamp: int) -> str:
    """Generate HMAC signature for test requests."""
    body_str = json.dumps(body)
    message = f"{timestamp}{body_str}"
    signature = hmac.new(
        settings.HMAC_SECRET.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return signature


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
    signature = generate_hmac_signature(body, timestamp)
    
    with patch("app.main.telegram_service.send_alert", new_callable=AsyncMock) as mock_send_alert:
        response = await test_client.post(
            "/post-call-webhook",
            json=body,
            headers={
                "X-API-Key": settings.API_KEY,
                "X-Signature": signature,
                "X-Timestamp": str(timestamp)
            }
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
    signature = generate_hmac_signature(body, timestamp)
    
    with patch("app.main.telegram_service.send_alert", new_callable=AsyncMock) as mock_send_alert:
        response = await test_client.post(
            "/post-call-webhook",
            json=body,
            headers={
                "X-API-Key": settings.API_KEY,
                "X-Signature": signature,
                "X-Timestamp": str(timestamp)
            }
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
    
    response = await test_client.post(
        "/post-call-webhook",
        json=body,
        headers={
            "X-API-Key": settings.API_KEY,
            "X-Signature": "invalid_signature",
            "X-Timestamp": str(timestamp)
        }
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
    
    response = await test_client.post(
        "/post-call-webhook",
        json=body,
        headers={
            "X-API-Key": settings.API_KEY,
            "X-Timestamp": str(int(time.time()))
        }
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
    signature = generate_hmac_signature(body, old_timestamp)
    
    response = await test_client.post(
        "/post-call-webhook",
        json=body,
        headers={
            "X-API-Key": settings.API_KEY,
            "X-Signature": signature,
            "X-Timestamp": str(old_timestamp)
        }
    )
    
    assert response.status_code == 401
    assert "too old" in response.json()["detail"].lower()
