from fastapi.testclient import TestClient

from app.main import app


def test_root_cache_headers_and_deploy_marker():
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "no-store" in response.headers.get("Cache-Control", "")
    assert 'id="deploy-marker"' in response.text
    assert "DEPLOY_MARKER=" in response.text
