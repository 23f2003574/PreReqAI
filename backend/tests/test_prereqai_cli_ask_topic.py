import json
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import app

pytestmark = pytest.mark.prereqai

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = "examples/prerequisites/sample-paper.pdf"


def _ask(*args):
    run = subprocess.run([sys.executable, "-m", "backend.cli", "prerequisites", "ask", SAMPLE, *args],
                         cwd=ROOT, capture_output=True, text=True, timeout=120)
    return run.returncode, run.stdout, run.stderr


def test_a_paper_concept_is_accepted_as_the_topic_case_insensitively():
    code, out, err = _ask("What is this?", "--topic", " softmax ", "--json")
    assert code == 0 and err == "" and json.loads(out)["status"] == "success"


def test_an_unknown_topic_is_a_usage_error_with_the_same_hint_as_the_api():
    code, out, err = _ask("What is this?", "--topic", "Cooking")
    assert code == 2 and out == "" and "unknown topic: 'Cooking'" in err

    with open(ROOT / SAMPLE, "rb") as handle:
        client = TestClient(app)
        session_id = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf")}).json()["session_id"]
    http = client.post(f"/api/session/{session_id}/question", json={"question": "What is this?", "topic": "Cooking"})
    assert http.status_code == 422 and http.json()["hint"] in err
