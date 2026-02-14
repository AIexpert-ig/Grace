from fastapi.testclient import TestClient

from app.main import app


def test_ws_handshake_on_path_with_call_id():
    client = TestClient(app)
    with client.websocket_connect("/llm-websocket/call_test") as ws:
        msg = ws.receive_json()
        assert msg["response_id"] == 0
        assert msg["content"] == ""
        assert msg["content_complete"] is True


def test_update_only_no_response():
    client = TestClient(app)
    with client.websocket_connect("/llm-websocket/call_test") as ws:
        ws.receive_json()
        ws.send_json({
            "interaction_type": "update_only",
            "transcript": [{"role": "user", "content": "Hello"}],
        })
        ws.send_json({
            "interaction_type": "response_required",
            "response_id": 7,
            "transcript": [{"role": "user", "content": "Hello"}],
        })
        response = ws.receive_json()
        assert response["response_id"] == 7
        assert response["content"].startswith("MARKER_9F6D:")


def test_response_required_marker():
    client = TestClient(app)
    with client.websocket_connect("/llm-websocket") as ws:
        ws.receive_json()
        ws.send_json({
            "interaction_type": "response_required",
            "response_id": 9,
            "transcript": [{"role": "user", "content": ""}],
        })
        response = ws.receive_json()
        assert response["response_id"] == 9
        assert response["content"].startswith("MARKER_9F6D:")
