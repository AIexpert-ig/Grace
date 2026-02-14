import time

from app import main as app_main


def test_empty_text_returns_clarifying():
    payload = {"interaction_type": "response_required", "transcript": [{"content": ""}]}
    text = app_main._get_latest_user_text(payload)
    assert app_main._is_unclear_text(text) is True
    assert app_main._clarify_response() in app_main._clarify_response()


def test_repetition_triggers_loop_breaker():
    call_id = "call-test"
    app_main._record_assistant(call_id, "I have noted that request.")
    app_main._record_assistant(call_id, "I have noted that request.")
    state = app_main._retell_state_for(call_id)
    candidate = "I have noted that request."
    assert candidate in state["last_assistant"]
    assert app_main._loop_break_response().startswith("I may be missing")


def test_user_repeat_within_window():
    call_id = "call-repeat"
    text = "Hello?"
    first = app_main._user_repeated_recent(call_id, text)
    time.sleep(0.01)
    second = app_main._user_repeated_recent(call_id, text)
    assert first is False
    assert second is True
