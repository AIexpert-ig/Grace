import pytest

from app.core.config import settings


def _set_setting(monkeypatch, name, value):
    monkeypatch.setitem(settings.__dict__, name, value)


@pytest.mark.asyncio
async def test_integration_test_endpoints_require_admin_token(monkeypatch, test_client):
    _set_setting(monkeypatch, "ADMIN_TOKEN", "secret")

    res = await test_client.get("/integrations/test/telegram")
    assert res.status_code == 401
    assert res.json()["error"] == "unauthorized"

    res = await test_client.get("/integrations/test/make")
    assert res.status_code == 401
    assert res.json()["error"] == "unauthorized"


@pytest.mark.asyncio
async def test_integration_test_endpoints_get_success(monkeypatch, test_client):
    _set_setting(monkeypatch, "ADMIN_TOKEN", "secret")

    res = await test_client.get(
        "/integrations/test/telegram",
        headers={"X-Admin-Token": "secret"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "triggered"

    res = await test_client.get(
        "/integrations/test/make",
        headers={"X-Admin-Token": "secret"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "triggered"
