"""Tests for the call webhook endpoint."""
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.core.config import settings


@pytest.mark.asyncio
async def test_post_call_webhook_high_urgency():
    """Test webhook processing for high urgency calls."""
    with patch("app.main.telegram_service.send_alert", new_callable=AsyncMock) as mock_send_alert:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post(
                "/post-call-webhook",
                json={
                    "caller_name": "John Doe",
                    "room_number": "101",
                    "callback_number": "+123456789",
                    "summary": "Guest is unhappy",
                    "urgency": "high"
                },
                headers={"X-API-Key": settings.API_KEY}
            )

        assert response.status_code == 200
        mock_send_alert.assert_called_once()
        assert "John Doe" in mock_send_alert.call_args[0][0]


@pytest.mark.asyncio
async def test_post_call_webhook_low_urgency():
    """Test webhook processing for low urgency calls."""
    with patch("app.main.telegram_service.send_alert", new_callable=AsyncMock) as mock_send_alert:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post(
                "/post-call-webhook",
                json={
                    "caller_name": "Jane Doe",
                    "room_number": "102",
                    "callback_number": "+987654321",
                    "summary": "Just asking about breakfast",
                    "urgency": "low"
                },
                headers={"X-API-Key": settings.API_KEY}
            )

        assert response.status_code == 200
        mock_send_alert.assert_not_called()


@pytest.mark.asyncio
async def test_post_call_webhook_invalid_api_key():
    """Test webhook with invalid API key."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/post-call-webhook",
            json={
                "caller_name": "John Doe",
                "room_number": "101",
                "callback_number": "+123456789",
                "summary": "Test",
                "urgency": "high"
            },
            headers={"X-API-Key": "invalid_key"}
        )

    assert response.status_code == 401
    assert "Invalid API Key" in response.json()["detail"]
