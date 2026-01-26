"""Integration tests for rate checking endpoint."""
from datetime import date, timedelta
import pytest
from httpx import Response

TODAY = date.today()
FUTURE_DATE = (TODAY + timedelta(days=5)).isoformat()
PAST_DATE = (TODAY - timedelta(days=1)).isoformat()

@pytest.mark.asyncio
async def test_check_rates_integration_not_found(test_client):
    """Integration test: Verify 404 response text."""
    # Date far in the future
    far_future = (TODAY + timedelta(days=500)).isoformat()
    response: Response = await test_client.post(
        "/check-rates",
        json={"check_in_date": far_future, "room_type": "standard"}
    )
    assert response.status_code == 404
    # FIXED: String alignment
    assert "No rates found for this date." in response.json()["detail"]

@pytest.mark.asyncio
async def test_check_rates_integration_past_date(test_client):
    """Integration test: Verify 400 response for past dates."""
    response: Response = await test_client.post(
        "/check-rates",
        json={"check_in_date": PAST_DATE, "room_type": "standard"}
    )
    # The API should catch the ValueError and return 400
    assert response.status_code == 400
    assert "past" in response.json()["detail"].lower()