import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_check_rates_standard():
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
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/check-rates", json={"check_in_date": "2026-01-22", "room_type": "suite"})
    
    assert response.status_code == 200
    assert response.json() == {
        "rate": "950",
        "currency": "AED",
        "availability": "High"
    }

@pytest.mark.asyncio
async def test_check_rates_no_availability():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/check-rates", json={"check_in_date": "2099-01-01"})
    
    assert response.status_code == 200
    assert response.json() == {"rate": "N/A", "availability": "None"}
