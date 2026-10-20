"""Marking a concept known twice is harmless; a concept outside the plan still fails."""
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.platform import platform

SAMPLE = "examples/prerequisites/sample-paper.pdf"


def test_marking_known_again_returns_the_same_plan():
    sid = platform.analyze(SAMPLE)["session_id"]
    first = platform.mark_concept_known(sid, "Probability")
    again = platform.mark_concept_known(sid, "probability")
    assert again["study_progress"] == first["study_progress"]
    assert "Probability" not in [item["concept"] for item in again["study_progress"]]


def test_unknown_concept_still_fails():
    sid = platform.analyze(SAMPLE)["session_id"]
    with pytest.raises(ValueError):
        platform.mark_concept_known(sid, "Not A Concept")


def test_http_repeat_known_answers_success_both_times():
    client = TestClient(app)
    with open(SAMPLE, "rb") as handle:
        sid = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf")}).json()["session_id"]
    url = f"/api/prerequisites/sessions/{sid}/known?concept=Probability"
    assert [client.post(url).status_code for _ in range(2)] == [200, 200]
