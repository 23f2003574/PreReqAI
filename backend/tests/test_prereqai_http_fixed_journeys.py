"""Over HTTP, end to end: a link pasted with wrapper characters is downloaded and analysed, and the tutor answers honestly for
a paper with no known concepts and for a quiz on a prerequisite (all three were previously covered through the CLI or helpers only)."""
from pathlib import Path

import fitz
import pytest
from fastapi.testclient import TestClient

from backend.ingestion.arxiv_resolver import ArxivResolver
from backend.main import app

pytestmark = pytest.mark.prereqai

SAMPLE = Path(__file__).resolve().parents[2] / "examples" / "prerequisites" / "sample-paper.pdf"


@pytest.fixture
def client():
    return TestClient(app)


def _upload(client, content):
    response = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", content, "application/pdf")})
    assert response.status_code == 200
    return response.json()["session_id"]


def _answer(client, session, question):
    response = client.post(f"/api/session/{session}/question", json={"question": question})
    assert response.status_code == 200
    return response.json()["responses"][0]["answer"]


def test_a_link_pasted_with_wrapper_characters_is_downloaded_and_analysed(client, monkeypatch, tmp_path):
    monkeypatch.setattr(ArxivResolver, "CACHE_DIRECTORY", tmp_path / "arxiv")
    requested = []
    monkeypatch.setattr(ArxivResolver, "_download", lambda self, url: requested.append(url) or SAMPLE.read_bytes())

    response = client.post("/api/prerequisites/analyze", data={"source": "<https://arxiv.org/abs/1706.03762>."})

    assert response.status_code == 200 and response.json()["report"]["learning_plan"]
    assert requested == ["https://arxiv.org/pdf/1706.03762.pdf"]


def test_a_non_arxiv_link_is_still_refused(client):
    response = client.post("/api/prerequisites/analyze", data={"source": "<https://example.com/paper.pdf>"})
    assert response.status_code == 422


def test_a_paper_with_no_known_concepts_is_not_declared_ready(client):
    document = fitz.open()
    document.new_page().insert_text((72, 72), "A Study of Bees\n\nAbstract\nBees are insects that make honey.\n", fontsize=11)
    session = _upload(client, document.tobytes())

    for question in ("Am I ready?", "What should I study first?"):
        answer = _answer(client, session, question)
        assert answer.startswith("No concepts this release knows were detected") and "You are ready" not in answer


def test_a_quiz_on_a_prerequisite_does_not_quiz_other_concepts(client):
    session = _upload(client, SAMPLE.read_bytes())

    assert _answer(client, session, "Quiz me on Calculus") == "There are no practice questions yet for Calculus."
    assert _answer(client, session, "Quiz me on Softmax").startswith("Softmax Q1")
