"""'Explain this concept', a follow-up the tutor itself suggests, is answered: from the topic when there is one, otherwise
by saying how to pick a concept."""
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import app

pytestmark = pytest.mark.prereqai

ROOT = Path(__file__).resolve().parents[2]
PAPER = "examples/prerequisites/sample-paper.pdf"
PLACEHOLDER = "tutoring model has not yet been configured"


def _cli(question, *flags):
    run = subprocess.run([sys.executable, "-m", "backend.cli", "prerequisites", "ask", PAPER, question, *flags],
                         cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert run.returncode == 0
    return run.stdout.splitlines()[0]


def test_with_a_topic_this_concept_is_the_topic():
    assert _cli("Explain this concept", "--topic", "Softmax") == _cli("What is Softmax?")
    assert _cli("Describe it", "--topic", "Probability").startswith("Probability: ")


def test_without_a_topic_the_answer_names_the_paper_concepts_to_pick_from():
    answer = _cli("Explain this concept")
    assert PLACEHOLDER not in answer and answer.startswith("Name the concept to explain")
    assert "Softmax" in answer and "Gradient Descent" in answer


def _session(client):
    with open(ROOT / PAPER, "rb") as pdf:
        return client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", pdf, "application/pdf")}).json()["session_id"]


def _ask(client, sid, question, **extra):
    return client.post(f"/api/session/{sid}/question", json={"question": question, **extra}).json()["responses"][0]["answer"]


def test_the_same_answers_over_http_and_other_questions_are_unchanged():
    client = TestClient(app)
    fresh = _session(client)
    assert _ask(client, fresh, "Explain this concept").startswith("Name the concept to explain")
    assert _ask(client, fresh, "What is softmax?").startswith("Softmax: ")
    assert PLACEHOLDER in _ask(client, fresh, "Tell me a joke")

    focused = _session(client)
    assert _ask(client, focused, "Explain this concept", topic="Softmax").startswith("Softmax: ")
    # the session keeps its topic, so the follow-up still means that concept
    assert _ask(client, focused, "Explain this concept").startswith("Softmax: ")
