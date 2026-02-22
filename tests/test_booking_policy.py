from app import main


def _noop(*_args, **_kwargs):
    return None


def test_booking_confirmation_blocked_without_booking_id(monkeypatch):
    monkeypatch.setattr(main, "_open_staff_ticket", _noop)
    monkeypatch.setattr(main, "_emit_event", _noop)
    context = {"booking_id": None, "rates": None}
    reply = "Your booking is confirmed. See you then!"
    result = main._apply_response_guards(reply, context, "book spa", "call-1")
    lowered = result.lower()
    assert "confirmed" not in lowered
    assert "see you then" not in lowered


def test_pricing_quote_blocked_without_rates(monkeypatch):
    monkeypatch.setattr(main, "_open_staff_ticket", _noop)
    monkeypatch.setattr(main, "_emit_event", _noop)
    context = {"booking_id": None, "rates": None}
    reply = "The rate is $200 per night."
    result = main._apply_response_guards(reply, context, "room rate", "call-2")
    assert "$" not in result


def test_booking_confirmation_allowed_with_booking_id(monkeypatch):
    monkeypatch.setattr(main, "_open_staff_ticket", _noop)
    monkeypatch.setattr(main, "_emit_event", _noop)
    context = {"booking_id": "spa_123", "rates": None}
    reply = "Your booking is confirmed. See you then!"
    result = main._apply_response_guards(reply, context, "book spa", "call-3")
    assert result == reply
