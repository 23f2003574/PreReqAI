"""The upload route turns the isolated worker's refusals into structured responses and keeps the server answering afterwards."""
import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api import prerequisite_routes
from backend.ingestion.pdf_guard import PdfGuardError
from backend.main import app

pytestmark = pytest.mark.prereqai
client = TestClient(app)
SAMPLE = Path(__file__).resolve().parents[2] / "examples" / "prerequisites" / "sample-paper.pdf"


@pytest.mark.parametrize("kind, status, code", [("timeout", "timeout", 504), ("resource_exhausted", "limit_exceeded", 413), ("too_many_pages", "limit_exceeded", 413), ("worker_failed", "failure", 400)])
def test_each_guard_failure_is_a_structured_response_and_the_server_keeps_answering(monkeypatch, tmp_path, kind, status, code):
    def refuse(path, **kwargs):
        raise PdfGuardError(kind, f"the worker said {kind}")

    monkeypatch.setattr("backend.ingestion.pdf_guard.guard_pdf", refuse)
    monkeypatch.setattr("tempfile.tempdir", str(tmp_path))
    analysed = []
    monkeypatch.setattr(prerequisite_routes.platform, "analyze", lambda *a, **k: analysed.append(a))
    response = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", io.BytesIO(b"%PDF-1.4 hostile"), "application/pdf")})
    body = response.json()
    assert body["status"] == status and body["stage"] == "ingestion" and f"the worker said {kind}" in body["detail"] and response.status_code == code
    assert analysed == [] and list(tmp_path.iterdir()) == []  # never analysed in the server, temp file removed
    assert client.get("/health").status_code == 200


def test_a_normal_paper_still_analyses_through_the_worker():
    response = client.post("/api/prerequisites/analyze", files={"paper": ("sample.pdf", SAMPLE.read_bytes(), "application/pdf")})
    assert response.status_code == 200 and response.json()["status"] == "success"
