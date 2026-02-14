import pytest


@pytest.mark.asyncio
async def test_root_cache_headers_and_build_stamp(test_client):
    response = await test_client.get("/")
    assert response.status_code == 200
    cache_control = response.headers.get("cache-control", "").lower()
    assert "no-store" in cache_control
    assert "max-age=0" in cache_control.replace(" ", "")
    assert "id=\"build-marker\"" in response.text
