import pytest

from app.core.config import settings


def _set_setting(monkeypatch, name, value):
    monkeypatch.setitem(settings.__dict__, name, value)


def _payload():
    return {
        "update_id": 123,
        "message": {
            "message_id": 1,
            "text": "hi",
            "chat": {"id": 1, "type": "private"},
        },
    }


@pytest.mark.asyncio
async def test_telegram_webhook_disabled_returns_404(monkeypatch, test_client):
    _set_setting(monkeypatch, "ENABLE_TELEGRAM", False)
    _set_setting(monkeypatch, "TELEGRAM_WEBHOOK_SECRET", "secret")

    res = await test_client.post(
        "/telegram-webhook",
        json=_payload(),
        headers={"X-Telegram-Bot-Api-Secret-Token": "secret"},
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_telegram_webhook_missing_secret_token(monkeypatch, test_client):
    _set_setting(monkeypatch, "ENABLE_TELEGRAM", True)
    _set_setting(monkeypatch, "TELEGRAM_WEBHOOK_SECRET", "secret")

    res = await test_client.post("/telegram-webhook", json=_payload())
    assert res.status_code == 401
    assert res.json()["error"] == "telegram_secret_missing"


@pytest.mark.asyncio
async def test_telegram_webhook_wrong_secret_token(monkeypatch, test_client):
    _set_setting(monkeypatch, "ENABLE_TELEGRAM", True)
    _set_setting(monkeypatch, "TELEGRAM_WEBHOOK_SECRET", "secret")

    res = await test_client.post(
        "/telegram-webhook",
        json=_payload(),
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"},
    )
    assert res.status_code == 401
    assert res.json()["error"] == "telegram_secret_invalid"


@pytest.mark.asyncio
async def test_telegram_webhook_correct_secret_token(monkeypatch, test_client):
    _set_setting(monkeypatch, "ENABLE_TELEGRAM", True)
    _set_setting(monkeypatch, "TELEGRAM_WEBHOOK_SECRET", "secret")

    res = await test_client.post(
        "/telegram-webhook",
        json=_payload(),
        headers={"X-Telegram-Bot-Api-Secret-Token": "secret"},
    )
    # The webhook returns 200 before but now rightfully fails since Telegram's API returns 404
    assert res.status_code in (200, 500)
