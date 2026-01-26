"""Tests for the rate checking endpoint."""
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.core.database import get_db
from app.db_models import Rate


@pytest.mark.asyncio
async def test_check_rates_standard():
    """Test checking rates for a standard room."""
    check_in_date = date.today() + timedelta(days=1)
    # Mock database rate
    mock_rate = Rate(
        id=1,
        check_in_date=check_in_date,
        standard_rate=500,
        suite_rate=950,
        availability="High"
    )

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_rate
    mock_session.execute.return_value = mock_result

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post(
                "/check-rates",
                json={"check_in_date": check_in_date.isoformat()}
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "rate": "500",
        "currency": "AED",
        "availability": "High"
    }


@pytest.mark.asyncio
async def test_check_rates_suite():
    """Test checking rates for a suite room."""
    check_in_date = date.today() + timedelta(days=1)
    # Mock database rate
    mock_rate = Rate(
        id=1,
        check_in_date=check_in_date,
        standard_rate=500,
        suite_rate=950,
        availability="High"
    )

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_rate
    mock_session.execute.return_value = mock_result

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post(
                "/check-rates",
                json={"check_in_date": check_in_date.isoformat(), "room_type": "suite"}
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "rate": "950",
        "currency": "AED",
        "availability": "High"
    }


@pytest.mark.asyncio
async def test_check_rates_no_availability():
    """Test checking rates when no availability exists."""
    check_in_date = date.today() + timedelta(days=30)
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post(
                "/check-rates",
                json={"check_in_date": check_in_date.isoformat()}
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert "No rates available" in response.json()["detail"]
