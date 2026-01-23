"""Tests for the rate checking endpoint."""
from datetime import date
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.db_models import Rate


@pytest.mark.asyncio
async def test_check_rates_standard():
    """Test checking rates for a standard room."""
    # Mock database rate
    mock_rate = Rate(
        id=1,
        check_in_date=date(2026, 1, 22),
        standard_rate=500,
        suite_rate=950,
        availability="High"
    )

    with patch("app.main.get_db") as mock_get_db:
        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_rate
        mock_session.execute.return_value = mock_result
        mock_get_db.return_value.__aenter__.return_value = mock_session

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post("/check-rates", json={"check_in_date": "2026-01-22"})

        assert response.status_code == 200
        assert response.json() == {
            "rate": "500",
            "currency": "AED",
            "availability": "High"
        }


@pytest.mark.asyncio
async def test_check_rates_suite():
    """Test checking rates for a suite room."""
    # Mock database rate
    mock_rate = Rate(
        id=1,
        check_in_date=date(2026, 1, 22),
        standard_rate=500,
        suite_rate=950,
        availability="High"
    )

    with patch("app.main.get_db") as mock_get_db:
        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_rate
        mock_session.execute.return_value = mock_result
        mock_get_db.return_value.__aenter__.return_value = mock_session

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post(
                "/check-rates",
                json={"check_in_date": "2026-01-22", "room_type": "suite"}
            )

        assert response.status_code == 200
        assert response.json() == {
            "rate": "950",
            "currency": "AED",
            "availability": "High"
        }


@pytest.mark.asyncio
async def test_check_rates_no_availability():
    """Test checking rates when no availability exists."""
    with patch("app.main.get_db") as mock_get_db:
        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        mock_get_db.return_value.__aenter__.return_value = mock_session

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post("/check-rates", json={"check_in_date": "2099-01-01"})

        assert response.status_code == 404
        assert "No rates available" in response.json()["detail"]
