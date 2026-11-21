from src.core_specs.configuration.config_loader import BACKEND_ROOT, resolve_backend_path


def test_health_check_reports_ok(client):
    response = client.get("/")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "dreamguard-backend"


def test_cors_allows_configured_dashboard_origin(client):
    response = client.options(
        "/",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )

    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_rejects_unknown_origin(client):
    response = client.options(
        "/",
        headers={"Origin": "http://untrusted.invalid", "Access-Control-Request-Method": "GET"},
    )

    assert "access-control-allow-origin" not in response.headers


def test_config_paths_resolve_from_backend_root():
    assert resolve_backend_path("logs").startswith(BACKEND_ROOT)
