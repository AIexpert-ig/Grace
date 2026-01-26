"""Unit tests for Grace rates."""
import pytest
from datetime import date, timedelta

def test_check_rates_no_availability(test_client):
    """Verify 404 response matches the 'No rates found' string."""
    # Date far in the future
    future_date = (date.today() + timedelta(days=400)).isoformat()
    
    response = test_client.post(
        "/check-rates",
        json={"check_in_date": future_date, "room_type": "standard"}
    )
    
    assert response.status_code == 404
    # This MUST match your app/main.py exactly
    assert "No rates found for this date." in response.json()["detail"]