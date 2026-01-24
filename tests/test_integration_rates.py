"""Integration tests for rate checking endpoint with real database."""
from datetime import date, timedelta

import pytest
from app.db_models import Rate


# Generate dynamic dates to avoid stale hardcoding.
FUTURE_DATE_OBJ = date.today() + timedelta(days=5)
FUTURE_DATE = FUTURE_DATE_OBJ.isoformat()
FUTURE_DATE_2_OBJ = FUTURE_DATE_OBJ + timedelta(days=1)
FUTURE_DATE_2 = FUTURE_DATE_2_OBJ.isoformat()
PAST_DATE = (date.today() - timedelta(days=5)).isoformat()


@pytest.mark.asyncio
async def test_check_rates_integration_standard(test_client, sample_rate):
    """Integration test: Check rates for standard room with real database."""
    response = await test_client.post(
        "/check-rates",
        json={"check_in_date": FUTURE_DATE, "room_type": "standard"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["rate"] == "500"
    assert data["currency"] == "AED"
    assert data["availability"] == "High"


@pytest.mark.asyncio
async def test_check_rates_integration_suite(test_client, sample_rate):
    """Integration test: Check rates for suite room with real database."""
    response = await test_client.post(
        "/check-rates",
        json={"check_in_date": FUTURE_DATE, "room_type": "suite"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["rate"] == "950"
    assert data["currency"] == "AED"
    assert data["availability"] == "High"


@pytest.mark.asyncio
async def test_check_rates_integration_not_found(test_client):
    """Integration test: 404 when rate doesn't exist in database."""
    response = await test_client.post(
        "/check-rates",
        json={"check_in_date": FUTURE_DATE, "room_type": "standard"}
    )
    
    assert response.status_code == 404
    assert "No rates available" in response.json()["detail"]


@pytest.mark.asyncio
async def test_check_rates_integration_past_date(test_client):
    """Integration test: Validation error for past date."""
    response = await test_client.post(
        "/check-rates",
        json={"check_in_date": PAST_DATE, "room_type": "standard"}
    )
    
    assert response.status_code == 422  # Validation error
    assert "past" in response.json()["detail"][0]["msg"].lower()


@pytest.mark.asyncio
async def test_check_rates_integration_multiple_rates(test_client, db_session):
    """Integration test: Multiple rates in database."""
    from app.db_models import Rate
    
    # Add multiple rates
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
    db_session.add(rate1)
    db_session.add(rate2)
    await db_session.commit()
    
    # Test first rate
    response1 = await test_client.post(
        "/check-rates",
        json={"check_in_date": FUTURE_DATE, "room_type": "standard"}
    )
    assert response1.status_code == 200
    assert response1.json()["rate"] == "500"
    
    # Test second rate
    response2 = await test_client.post(
        "/check-rates",
        json={"check_in_date": FUTURE_DATE_2, "room_type": "suite"}
    )
    assert response2.status_code == 200
    assert response2.json()["rate"] == "1000"
