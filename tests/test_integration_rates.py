"""Integration tests for rate checking endpoint with real database."""
from datetime import date, timedelta
import pytest
from httpx import Response
from app.db_models import Rate

# --- DYNAMIC DATE GENERATION ---
# This ensures tests never fail because a hardcoded date became "the past"
TODAY = date.today()
FUTURE_DATE_OBJ = TODAY + timedelta(days=5)
FUTURE_DATE = FUTURE_DATE_OBJ.isoformat()

FUTURE_DATE_2_OBJ = TODAY + timedelta(days=10)
FUTURE_DATE_2 = FUTURE_DATE_2_OBJ.isoformat()

# Past date is always relative to the execution time
PAST_DATE = (TODAY - timedelta(days=1)).isoformat()

@pytest.mark.asyncio
async def test_check_rates_integration_standard(test_client, sample_rate):
    """Integration test: Check rates for standard room."""
    response: Response = await test_client.post(
        "/check-rates",
        json={"check_in_date": FUTURE_DATE, "room_type": "standard"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["currency"] == "AED"
    assert "rate" in data


@pytest.mark.asyncio
async def test_check_rates_integration_not_found(test_client):
    """Integration test: 404 when rate doesn't exist."""
    # Using a date far in the future to ensure it's not in the DB
    far_future_date = (TODAY + timedelta(days=365)).isoformat()
    
    response: Response = await test_client.post(
        "/check-rates",
        json={"check_in_date": far_future_date, "room_type": "standard"}
    )
    
    assert response.status_code == 404
    # MATCHED: Aligned with the 'No rates found for this date.' message in app/main.py
    assert "No rates found for this date." in response.json()["detail"]


@pytest.mark.asyncio
async def test_check_rates_integration_past_date(test_client):
    """Integration test: Validation error for past date."""
    response: Response = await test_client.post(
        "/check-rates",
        json={"check_in_date": PAST_DATE, "room_type": "standard"}
    )
    
    # Validation errors are 400
    assert response.status_code == 400 
    assert "past" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_check_rates_integration_multiple_rates(test_client, db_session):
    """Integration test: Handling multiple records efficiently."""
    rate1 = Rate(
        check_in_date=FUTURE_DATE_OBJ,
        standard_rate=500,
        suite_rate=950,
        availability="High"
    )
    rate2 = Rate(
        check_in_date=FUTURE_DATE_2_OBJ,
        standard_rate=550,
        suite_rate=1000,
        availability="Low"
    )
    db_session.add_all([rate1, rate2])
    await db_session.commit()
    
    # Verify first rate
    resp1 = await test_client.post(
        "/check-rates",
        json={"check_in_date": FUTURE_DATE, "room_type": "standard"}
    )
    assert resp1.json()["rate"] == "500"
    
    # Verify second rate
    resp2 = await test_client.post(
        "/check-rates",
        json={"check_in_date": FUTURE_DATE_2, "room_type": "suite"}
    )
    assert resp2.json()["rate"] == "1000"