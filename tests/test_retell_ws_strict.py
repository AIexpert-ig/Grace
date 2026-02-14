from fastapi.testclient import TestClient

from app import main as app_main
from app.main import app


class DummyResponse:
    def __init__(self, text: str):
        self.text = text


class DummyModel:
    def __init__(self, text: str):
        self._text = text

    def generate_content(self, _messages):
        return DummyResponse(self._text)


def test_update_only_no_response():
    client = TestClient(app)
    with client.websocket_connect("/llm-websocket") as ws:
        init_msg = ws.receive_json()
        assert init_msg["response_id"] == 0
        ws.send_json({
            "interaction_type": "update_only",
            "transcript": [{"role": "user", "content": "Hello"}],
        })
        ws.send_json({
            "interaction_type": "response_required",
            "response_id": 1,
            "transcript": [{"role": "user", "content": "Hello"}],
        })
        response = ws.receive_json()
        assert response["response_id"] == 1


def test_response_required_greeting_when_empty():
    client = TestClient(app)
    with client.websocket_connect("/llm-websocket") as ws:
        ws.receive_json()
        ws.send_json({
            "interaction_type": "response_required",
            "response_id": 2,
            "transcript": [{"role": "user", "content": ""}],
        })
        response = ws.receive_json()
        assert "assist" in response["content"].lower()


def test_repeated_assistant_reply_triggers_breaker(monkeypatch):
    def fake_model(*_args, **_kwargs):
        return DummyModel("Test reply")

    monkeypatch.setattr(app_main.genai, "GenerativeModel", fake_model)

    client = TestClient(app)
    with client.websocket_connect("/llm-websocket") as ws:
        ws.receive_json()
        ws.send_json({
            "interaction_type": "response_required",
            "response_id": 10,
            "transcript": [{"role": "user", "content": "Need towels"}],
        })
        first = ws.receive_json()
        assert first["content"] == "Test reply"

        ws.send_json({
            "interaction_type": "response_required",
            "response_id": 11,
            "transcript": [{"role": "user", "content": "Need towels"}],
        })
        second = ws.receive_json()
        assert second["content"] != "Test reply"
        assert "assist" in second["content"].lower()
