"""GET /health: a cheap liveness probe that reports the release version and needs no session or upload."""
from fastapi.testclient import TestClient

from backend.main import app
from backend.version import __version__

client = TestClient(app)


def test_health_reports_ok_and_the_release_version():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    analysis = body.pop("analysis")  # the analysis slots in use: tested in test_prereqai_health_slots.py
    assert body == {"status": "ok", "service": "PreReqAI", "version": __version__} and set(analysis) == {"limit", "active"}


def test_health_is_read_only():
    assert client.post("/health").status_code == 405
