"""Integration tests for Grace rates."""
from datetime import date, timedelta
import pytest

TODAY = date.today()
# Using a date that is definitely today to avoid "past" errors during the test run
VALID_DATE = TODAY.isoformat()
PAST_DATE = (TODAY - timedelta(days=1)).isoformat()

@pytest.mark.asyncio
async def test_check_rates_integration_past_date(test_client):
    """Verify 400 response for past dates without crashing."""
    response = await test_client.post(
        "/check-rates",
        json={"check_in_date": PAST_DATE, "room_type": "standard"}
    )
    # If this still throws ValueError, it means your app/main.py 
    # try/except block isn't catching it correctly.
    assert response.status_code == 400
    assert "past" in response.json()["detail"].lower()