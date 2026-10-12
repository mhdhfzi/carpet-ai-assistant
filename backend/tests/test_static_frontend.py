"""In production the backend also serves the built frontend from STATIC_DIR."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


@pytest.fixture
def static_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    (tmp_path / "index.html").write_text("<h1>demo</h1>", encoding="utf-8")
    (tmp_path / "admin.html").write_text("<h1>dashboard</h1>", encoding="utf-8")
    (tmp_path / "widget.js").write_text("console.log('widget')", encoding="utf-8")
    monkeypatch.setenv("STATIC_DIR", str(tmp_path))
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        yield client
    get_settings.cache_clear()


def test_frontend_files_are_served(static_client: TestClient) -> None:
    assert static_client.get("/").text == "<h1>demo</h1>"
    assert static_client.get("/admin.html").text == "<h1>dashboard</h1>"
    assert "javascript" in static_client.get("/widget.js").headers["content-type"]


def test_api_routes_take_priority_over_files(static_client: TestClient) -> None:
    assert static_client.get("/health").json()["status"] == "ok"
    assert static_client.get("/api/bookings").status_code == 401  # still protected


def test_no_static_files_without_static_dir() -> None:
    assert TestClient(create_app()).get("/").status_code == 404
