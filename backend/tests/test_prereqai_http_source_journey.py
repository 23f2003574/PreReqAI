"""An arXiv link or DOI can start the HTTP journey (analyze -> study -> plan) without uploading a file."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.ingestion.arxiv_resolver import ArxivResolver
from backend.main import app

SAMPLE = str(Path(__file__).resolve().parents[2] / "examples/prerequisites/sample-paper.pdf")
client = TestClient(app)


@pytest.fixture
def fetched(monkeypatch):
    seen = []
    monkeypatch.setattr(ArxivResolver, "resolve", lambda self, source: seen.append(source.identifier) or SAMPLE)
    return seen


def test_arxiv_source_runs_the_whole_journey(fetched):
    response = client.post("/api/prerequisites/analyze", data={"source": "https://arxiv.org/abs/1706.03762", "known": "Linear Algebra"})
    body = response.json()
    assert response.status_code == 200 and body["status"] == "success" and fetched == ["1706.03762"]
    sid = body["session_id"]

    studied = client.post(f"/api/prerequisites/sessions/{sid}/studied", params={"concept": "Probability"})
    assert studied.status_code == 200
    assert client.get(f"/api/session/{sid}/plan").status_code == 200
    assert client.get(f"/api/session/{sid}").status_code == 200


def test_arxiv_doi_source_is_accepted(fetched):
    response = client.post("/api/prerequisites/analyze", data={"source": "10.48550/arXiv.1706.03762"})
    assert response.status_code == 200 and fetched == ["1706.03762"]


@pytest.mark.parametrize("data", [{}, {"source": "10.48550/arXiv.1706.03762", "_both": "1"}])
def test_exactly_one_of_paper_and_source_is_required(data, fetched):
    files = {"paper": ("p.pdf", open(SAMPLE, "rb"), "application/pdf")} if "_both" in data else None
    response = client.post("/api/prerequisites/analyze", data={k: v for k, v in data.items() if k != "_both"}, files=files)
    assert response.status_code == 422 and response.json()["stage"] == "input" and fetched == []


@pytest.mark.parametrize("source", ["/etc/passwd", SAMPLE, "paper.pdf", "just some text"])
def test_a_server_path_or_other_text_is_never_read_as_a_source(source, fetched):
    response = client.post("/api/prerequisites/analyze", data={"source": source})
    assert response.status_code == 422 and "arXiv link or a DOI" in response.json()["detail"] and fetched == []
