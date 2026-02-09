import json

import pytest

from app.core.config import settings


def _set_setting(monkeypatch, name, value):
    monkeypatch.setitem(settings.__dict__, name, value)


class DummyBus:
    def __init__(self):
        self.published = []

    async def publish(self, envelope):
        self.published.append(envelope)
        return None


@pytest.mark.asyncio
async def test_status_allowed_for_non_admin(monkeypatch):
    _set_setting(monkeypatch, "TELEGRAM_ADMIN_IDS", "123")

    from app.services import telegram_bot

    result = await telegram_bot.handle_command("/status", user_id=999, bus=DummyBus())
    assert result["status"] == "ok"


@pytest.mark.asyncio
async def test_last_denied_for_non_admin(monkeypatch):
    _set_setting(monkeypatch, "TELEGRAM_ADMIN_IDS", "123")

    from app.services import telegram_bot

    result = await telegram_bot.handle_command("/last", user_id=999, bus=DummyBus())
    assert result["error"] == "unauthorized"


@pytest.mark.asyncio
async def test_escalate_rejects_bad_json(monkeypatch):
    _set_setting(monkeypatch, "TELEGRAM_ADMIN_IDS", "123")

    from app.services import telegram_bot

    result = await telegram_bot.handle_command("/escalate {bad json}", user_id=123, bus=DummyBus())
    assert result["error"] == "invalid_json"


@pytest.mark.asyncio
async def test_escalate_publishes_for_admin(monkeypatch):
    _set_setting(monkeypatch, "TELEGRAM_ADMIN_IDS", "123")

    from app.services import telegram_bot

    payload = {"guest_name": "Test", "room_number": "101"}
    text = f"/escalate {json.dumps(payload)}"
    bus = DummyBus()

    result = await telegram_bot.handle_command(text, user_id=123, bus=bus)
    assert result["status"] == "accepted"
    assert len(bus.published) == 1
    envelope = bus.published[0]
    assert envelope.source == "telegram"
    assert envelope.type == "escalation.create"
