import pytest

from app.core.config import settings


def _set_setting(monkeypatch, name, value):
    monkeypatch.setitem(settings.__dict__, name, value)


@pytest.mark.asyncio
async def test_flags_off_no_side_effects(monkeypatch, test_client):
    _set_setting(monkeypatch, "ENABLE_MAKE_WEBHOOKS", False)
    _set_setting(monkeypatch, "ENABLE_RETELL_SIMULATION", False)
    _set_setting(monkeypatch, "ENABLE_TELEGRAM", False)

    calls = {"count": 0}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            calls["count"] += 1
            class Dummy:
                status_code = 200
            return Dummy()

    monkeypatch.setattr(
        "app.services.make_integration.httpx.AsyncClient", FakeClient, raising=True
    )

    res_make_in = await test_client.post("/webhooks/make/in", json={})
    res_make_trigger = await test_client.post("/integrations/make/trigger", json={})
    res_retell = await test_client.post("/webhooks/retell/simulate", json={})

    assert res_make_in.status_code == 404
    assert res_make_trigger.status_code == 404
    assert res_retell.status_code == 404
    assert calls["count"] == 0
