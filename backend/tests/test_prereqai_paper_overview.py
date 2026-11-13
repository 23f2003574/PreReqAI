"""'Summarize this paper' (a follow-up the tutor itself suggests) is answered from the analysis, through the CLI and HTTP."""
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.prereqai

ROOT = Path(__file__).resolve().parents[2]
PAPER = "examples/prerequisites/sample-paper.pdf"
PLACEHOLDER = "tutoring model has not yet been configured"


def _cli(question, *flags):
    run = subprocess.run([sys.executable, "-m", "backend.cli", "prerequisites", "ask", PAPER, question, *flags],
                         cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert run.returncode == 0
    return run.stdout.splitlines()[0]


def test_summarize_this_paper_gives_title_concepts_difficulty_and_readiness():
    answer = _cli("Summarize this paper")
    assert answer.startswith("Attention Is All You Need (PreReqAI sample paper) covers 6 concepts: Transformer, Attention")
    assert "Difficulty: Advanced." in answer  # 47 hours of study, above the 4-subject band and "Preparation left: about 47 hours." in answer
    assert "Readiness: Preparation Required (0 of 4 planned concepts ready)." in answer


def test_the_overview_follows_the_learners_progress():
    answer = _cli("Give me an overview", "--studied", "Probability")
    assert "Preparation left: about 37 hours." in answer and "(1 of 4 planned concepts ready)" in answer


def test_a_named_concept_still_gets_its_definition_and_the_suggested_followup_is_no_longer_a_dead_end():
    assert _cli("Summarize attention").startswith("Attention: ")
    assert PLACEHOLDER not in _cli("Summarize this paper")


def test_the_same_overview_is_served_over_http_and_is_suggested_as_a_followup():
    from fastapi.testclient import TestClient
    from backend.main import app

    client = TestClient(app)
    with open(ROOT / PAPER, "rb") as pdf:
        sid = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", pdf, "application/pdf")}).json()["session_id"]
    reply = client.post(f"/api/session/{sid}/question", json={"question": "Summarize this paper"}).json()["responses"][0]
    assert reply["answer"] == _cli("Summarize this paper")
    other = client.post(f"/api/session/{sid}/question", json={"question": "x"}).json()["responses"][0]
    assert "Summarize this paper" in other["suggested_followups"]
