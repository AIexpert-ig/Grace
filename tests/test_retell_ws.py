from fastapi.testclient import TestClient

from app.main import app


def test_retell_update_only_no_response():
    client = TestClient(app)
    with client.websocket_connect("/llm-websocket") as ws:
        init_msg = ws.receive_json()
        assert init_msg["response_id"] == 0
        assert init_msg["content"] == ""
        assert init_msg["content_complete"] is True

        ws.send_json({
            "interaction_type": "update_only",
            "transcript": [{"role": "user", "content": "Hello?"}],
        })

        ws.send_json({
            "interaction_type": "response_required",
            "response_id": 5,
            "transcript": [{"role": "user", "content": "Hello?"}],
        })

        response = ws.receive_json()
        assert response["response_id"] == 5
        assert "assist" in response["content"].lower()


def test_retell_response_required_empty_text():
    client = TestClient(app)
    with client.websocket_connect("/llm-websocket") as ws:
        ws.receive_json()
        ws.send_json({
            "interaction_type": "response_required",
            "response_id": 2,
            "transcript": [{"role": "user", "content": ""}],
        })
        response = ws.receive_json()
        assert response["response_id"] == 2
        assert "assist" in response["content"].lower()
