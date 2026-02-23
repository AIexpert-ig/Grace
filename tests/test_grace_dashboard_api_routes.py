import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from Grace.app.api.routes import router as dashboard_router


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("path", "limit"),
    [
        ("/api/tickets", 1),
        ("/api/events", 5),
        ("/api/calls", 2),
        ("/api/staff", 10),
    ],
)
async def test_grace_dashboard_api_routes_return_200_and_list(path: str, limit: int):
    app = FastAPI()
    app.include_router(dashboard_router, prefix="/api")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(path, params={"limit": limit})

    assert response.status_code == 200
    assert isinstance(response.json(), list)

