from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_committed_openapi_schema_matches_the_api():
    from export_openapi import OUTPUT_PATH, render_schema

    assert OUTPUT_PATH == REPO_ROOT / "frontend" / "openapi.json"
    assert OUTPUT_PATH.read_text(encoding="utf-8") == render_schema(), (
        "frontend/openapi.json is out of date: run `python export_openapi.py` in backend/ "
        "and `npm run gen:api` in frontend/"
    )


def test_dashboard_build_is_served_under_dashboard(client):
    import main

    if not main.DASHBOARD_DIR.is_dir():
        pytest.skip("Dashboard not built (run `npm run build` in frontend/)")
    response = client.get("/dashboard/")
    assert response.status_code == 200
    assert "DreamGuard Safety Supervisor" in response.text
    assert client.get("/").json()["service"] == "dreamguard-backend"
