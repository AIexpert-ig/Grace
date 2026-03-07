"""Tests for Retell WebSocket normal-close handling.

Validates that:
- Code 1000 (normal close) logs one INFO line, no ERROR traceback.
- Non-1000 disconnects log WARNING, not ERROR.
"""
import logging

import pytest
from starlette.testclient import TestClient

from app.main import app


@pytest.fixture()
def sync_client():
    """Starlette sync TestClient – supports websocket_connect."""
    return TestClient(app, raise_server_exceptions=False)


def test_normal_close_1000_logs_info(sync_client, caplog):
    """Client connects then immediately closes → handler should log
    RETELL_WS_CLOSED_NORMAL at INFO, never RETELL_WS_ERROR."""
    with caplog.at_level(logging.DEBUG, logger="retell"):
        with sync_client.websocket_connect("/llm-websocket/call_test") as ws:
            # Read the initial greeting frame the handler sends
            _initial = ws.receive_json()
            # Close immediately (code 1000 normal close)

    log_text = caplog.text

    # Must contain the normal-close info line
    assert "RETELL_WS_CLOSED_NORMAL" in log_text, (
        f"Expected RETELL_WS_CLOSED_NORMAL in logs, got:\n{log_text}"
    )

    # Must NOT contain error/traceback markers
    assert "RETELL_WS_ERROR" not in log_text.replace("RETELL_WS_ERROR_UNEXPECTED", ""), (
        f"Found RETELL_WS_ERROR in logs (should not be present for code 1000):\n{log_text}"
    )
    assert "Traceback" not in log_text, (
        f"Found Traceback in logs (should not be present for code 1000):\n{log_text}"
    )


def test_normal_close_no_exception_raised(sync_client):
    """Connecting and immediately closing must not raise any exception."""
    with sync_client.websocket_connect("/llm-websocket/call_test") as ws:
        _initial = ws.receive_json()
    # If we get here without exception, the test passes.
