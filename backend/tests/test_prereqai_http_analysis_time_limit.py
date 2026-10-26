"""PREREQAI_MAX_ANALYSIS_SECONDS gives HTTP analyses the same time limit the CLI has with --max-seconds."""
import pytest
from fastapi.testclient import TestClient

from backend.main import app

PAPER = "examples/prerequisites/sample-paper.pdf"
client = TestClient(app)


def _analyze():
    with open(PAPER, "rb") as handle:
        return client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf")})


def test_a_tiny_limit_stops_the_analysis_with_413(monkeypatch):
    monkeypatch.setenv("PREREQAI_MAX_ANALYSIS_SECONDS", "0.000001")
    response = _analyze()
    assert response.status_code == 413
    assert response.json()["status"] == "limit_exceeded" and "time limit" in response.json()["detail"]


@pytest.mark.parametrize("value", ["", "  ", "abc", "0", "-5", "nan", "inf"])
def test_unset_or_unusable_values_mean_no_limit(monkeypatch, value):
    monkeypatch.setenv("PREREQAI_MAX_ANALYSIS_SECONDS", value)
    assert _analyze().status_code == 200


def test_a_generous_limit_does_not_change_a_normal_analysis(monkeypatch):
    monkeypatch.setenv("PREREQAI_MAX_ANALYSIS_SECONDS", "600")
    body = _analyze().json()
    assert body["status"] == "success" and body["report"]["learning_plan"]
