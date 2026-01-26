"""Unit tests for Grace rates."""
import pytest
from datetime import date, timedelta

@pytest.mark.asyncio  # <--- Added this to handle async
async def test_check_rates_no_availability(test_client):
    """Verify 404 response matches the 'No rates found' string."""
    future_date = (date.today() + timedelta(days=400)).isoformat()
    
    # ADDED 'await' here
    response = await test_client.post(
        "/check-rates",
        json={"check_in_date": future_date, "room_type": "standard"}
    )
    
    assert response.status_code == 404
    assert "No rates found for this date." in response.json()["detail"]