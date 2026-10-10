"""An upload over the size limit is refused as `limit_exceeded` (HTTP 413) while it is being copied -- it is
never written out in full or analysed -- and a normal upload is unaffected."""
import io
from pathlib import Path

from fastapi.testclient import TestClient

from backend.api import prerequisite_routes
from backend.main import app

client = TestClient(app)
SAMPLE = Path(__file__).resolve().parents[2] / "examples" / "prerequisites" / "sample-paper.pdf"


def test_an_oversized_upload_is_refused_without_being_analysed_or_kept(monkeypatch, tmp_path):
    monkeypatch.setattr(prerequisite_routes, "MAX_UPLOAD_BYTES", 2 * 1024 * 1024)
    monkeypatch.setattr(prerequisite_routes, "_CHUNK_BYTES", 64 * 1024)
    monkeypatch.setattr("tempfile.tempdir", str(tmp_path))
    analysed = []
    monkeypatch.setattr(prerequisite_routes.platform, "analyze", lambda path: analysed.append(path))

    response = client.post("/api/prerequisites/analyze",
                           files={"paper": ("big.pdf", io.BytesIO(b"%PDF-1.4\n" + b"0" * (3 * 1024 * 1024)), "application/pdf")})

    body = response.json()
    assert response.status_code == 413 and body["status"] == "limit_exceeded" and body["stage"] == "analysis"
    assert "larger than the limit of 2097152 bytes" in body["detail"] and body["hint"]
    assert analysed == [] and list(tmp_path.iterdir()) == []  # not analysed, temp file removed


def test_a_normal_paper_is_still_analysed():
    response = client.post("/api/prerequisites/analyze",
                           files={"paper": ("paper.pdf", SAMPLE.read_bytes(), "application/pdf")})

    assert response.status_code == 200 and response.json()["status"] == "success"
