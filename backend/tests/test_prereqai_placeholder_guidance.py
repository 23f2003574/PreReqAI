"""A question the built-in tutor cannot answer says what it can answer, instead of ending on a bare placeholder."""
import json
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.tutor.rule_based_tutor import ANSWERABLE_HINT

pytestmark = pytest.mark.prereqai

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = "examples/prerequisites/sample-paper.pdf"


def _cli(question):
    run = subprocess.run([sys.executable, "-m", "backend.cli", "prerequisites", "ask", SAMPLE, question],
                         cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert run.returncode == 0
    return run.stdout


def test_an_unanswerable_question_lists_what_can_be_asked_in_the_cli_and_the_api():
    out = _cli("Why is the sky blue?")
    assert "A tutoring model has not yet been configured." in out and ANSWERABLE_HINT in out
    client = TestClient(app)
    with open(ROOT / SAMPLE, "rb") as handle:
        sid = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf")}).json()["session_id"]
    body = client.post(f"/api/session/{sid}/question", json={"question": "hello"}).json()
    assert any(ANSWERABLE_HINT in warning for warning in body["warnings"])


def test_an_answerable_question_does_not_get_the_hint():
    assert ANSWERABLE_HINT not in _cli("What should I study first?")
    assert ANSWERABLE_HINT not in _cli("Quiz me on Softmax")
