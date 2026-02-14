from fastapi.testclient import TestClient

from app.main import app


def test_ws_handshake_on_path_with_call_id():
    client = TestClient(app)
    with client.websocket_connect("/llm-websocket/call_test") as ws:
        msg = ws.receive_json()
        assert msg == {
            "response_id": 0,
            "content": "",
            "content_complete": True,
            "end_call": False,
        }


def test_update_only_no_response():
    client = TestClient(app)
    with client.websocket_connect("/llm-websocket/call_test") as ws:
        ws.receive_json()
        ws.send_json({
            "interaction_type": "update_only",
            "response_id": 99,
            "transcript": [{"role": "user", "content": "Hello"}],
        })
        ws.send_json({
            "interaction_type": "response_required",
            "response_id": 7,
            "transcript": [{"role": "user", "content": "Hello"}],
        })
        response = ws.receive_json()
        assert response["response_id"] == 7
        assert "response_type" not in response


def test_response_required_response_shape():
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
        assert isinstance(response["response_id"], int)
        assert "response_type" not in response
