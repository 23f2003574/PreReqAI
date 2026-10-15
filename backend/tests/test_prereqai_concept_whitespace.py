"""Concept names typed with stray or repeated whitespace match the study plan like the exact name does."""
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from backend.main import app

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = "examples/prerequisites/sample-paper.pdf"
client = TestClient(app)


def _cli(*flags):
    run = subprocess.run([sys.executable, "-m", "backend.cli", "prerequisites", "analyze", SAMPLE, *flags],
                         cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert run.returncode == 0
    return run.stdout


def test_known_and_studied_ignore_repeated_whitespace():
    out = _cli("--known", "  linear   algebra ", "--studied", "Neural\t Networks")
    assert "1. Probability (10h) -> 2. Calculus (10h) -> 3. Neural Networks (15h, studied)" in out
    assert "warning" not in out


def test_unmatched_name_is_still_reported_tidily_and_http_studied_normalises():
    assert "--known 'not a concept' is not in this paper's study plan" in _cli("--known", " not   a   concept")
    with (ROOT / SAMPLE).open("rb") as handle:
        sid = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf")}).json()["session_id"]
    ok = client.post(f"/api/prerequisites/sessions/{sid}/studied", params={"concept": " probability  "})
    assert ok.status_code == 200 and {c["concept"]: c["completed"] for c in ok.json()["study_progress"]}["Probability"]
    assert client.post(f"/api/prerequisites/sessions/{sid}/studied", params={"concept": "Prob ability"}).status_code != 200
