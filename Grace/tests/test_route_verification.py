import pytest


@pytest.mark.asyncio
async def test_build_and_openapi_routes(test_client):
    build_res = await test_client.get("/__build")
    assert build_res.status_code == 200
    build_data = build_res.json()
    assert "sha" in build_data
    assert build_data.get("service") == "Grace"
    assert "routes" in build_data
    assert "deadletter" in build_data["routes"]
    assert "make_ingress" in build_data["routes"]

    openapi_res = await test_client.get("/openapi.json")
    assert openapi_res.status_code == 200
    paths = openapi_res.json().get("paths", {})

    for route in (
        "/events/deadletter",
        "/webhooks/make/in",
        "/integrations/make/trigger",
        "/webhooks/retell/simulate",
        "/webhook",
    ):
        assert route in paths
