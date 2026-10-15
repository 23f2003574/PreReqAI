"""The example walkthrough only documents flags the CLI has and a reply shape the server returns."""
import re
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from backend.main import app

ROOT = Path(__file__).resolve().parents[2]
DOC = (ROOT / "examples/prerequisites/README.md").read_text()
SAMPLE = ROOT / "examples/prerequisites/sample-paper.pdf"


def _help(command):
    return subprocess.run([sys.executable, "-m", "backend.cli", "prerequisites", command, "--help"],
                          cwd=ROOT, capture_output=True, text=True, timeout=60).stdout


def test_every_documented_cli_flag_exists_in_the_help():
    flags = set(re.findall(r"(?<![\w-])(--[a-z][a-z-]+)", DOC)) - {"--port"}  # --port belongs to uvicorn
    assert {"--known", "--studied", "--resources"} <= flags
    available = _help("analyze") + _help("ask")
    assert [flag for flag in sorted(flags) if flag not in available] == []


def test_documented_question_reply_has_the_answer_under_responses_and_a_bad_reply_has_no_top_level_answer():
    client = TestClient(app)
    sid = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", SAMPLE.read_bytes(), "application/pdf")}).json()["session_id"]
    reply = client.post(f"/api/session/{sid}/question", json={"question": "What is attention?"}).json()
    assert reply["status"] == "success" and "answer" not in reply
    first = reply["responses"][0]
    assert first["answer"].startswith("Attention: A mechanism") and first["supporting_concepts"] == ["Attention"]
    assert "responses[0]" in DOC and "next_resources" in DOC


def test_documented_plan_checklist_exists_in_the_cli_and_over_http():
    assert "--plan-file" in DOC and "--plan-file" in _help("analyze")
    client = TestClient(app)
    sid = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", SAMPLE.read_bytes(), "application/pdf")}).json()["session_id"]
    assert "/api/session/$SID/plan" in DOC
    reply = client.get(f"/api/session/{sid}/plan")
    assert reply.status_code == 200 and reply.headers["content-type"].startswith("text/markdown")
    assert reply.text.startswith("# Study plan:") and "- [ ] 1. " in reply.text
