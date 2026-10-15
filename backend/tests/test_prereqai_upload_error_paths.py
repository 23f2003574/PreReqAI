"""A failed upload's error text names the uploaded file, never the server's temporary path."""
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)
SAMPLE = Path(__file__).resolve().parents[2] / "examples/prerequisites/sample-paper.pdf"


def test_bad_uploads_report_the_uploaded_filename_not_the_temp_path():
    for name, content in (("my-paper.pdf", b"not a pdf"), ("empty.pdf", b"")):
        response = client.post("/api/prerequisites/analyze", files={"paper": (name, content, "application/pdf")})
        body = response.json()
        text = str(body)
        assert response.status_code == 400 and body["status"] == "failure"
        assert tempfile.gettempdir() not in text and ".pdf'" not in text.replace(name, "")
        assert name in body["detail"] or "empty file" in body["detail"]


def test_path_free_errors_and_successful_uploads_are_unchanged():
    ok = client.post("/api/prerequisites/analyze", files={"paper": ("../../etc/p.pdf", SAMPLE.read_bytes(), "application/pdf")})
    assert ok.status_code == 200 and ok.json()["status"] == "success"
    missing = client.post("/api/prerequisites/analyze")
    assert missing.status_code == 422 and tempfile.gettempdir() not in str(missing.json())
