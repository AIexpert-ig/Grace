"""Tests for Retell WebSocket protocol basics.

Validates the initial handshake frame that _retell_ws_handler sends on connect.
"""
import pytest
from starlette.testclient import TestClient

from app.main import app


@pytest.fixture()
def sync_client():
    """Starlette sync TestClient – supports websocket_connect."""
    return TestClient(app, raise_server_exceptions=False)


def test_ws_accepts_and_sends_initial_frame(sync_client):
    """Upon connect the handler should send a JSON frame with response_id=0
    and content_complete=True."""
    with sync_client.websocket_connect("/llm-websocket/call_test") as ws:
        frame = ws.receive_json()
        assert frame["response_id"] == 0
        assert frame["content_complete"] is True
        assert frame["end_call"] is False


def test_ws_root_path_also_works(sync_client):
    """The /llm-websocket (without call_id) endpoint should also work."""
    with sync_client.websocket_connect("/llm-websocket") as ws:
        frame = ws.receive_json()
        assert frame["response_id"] == 0
        assert frame["content_complete"] is True
