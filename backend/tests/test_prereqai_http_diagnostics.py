import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from backend.main import app

SAMPLE = Path(__file__).resolve().parents[2] / "examples" / "prerequisites" / "sample-paper.pdf"
client = TestClient(app)


def _post(content, **data):
    return client.post("/api/prerequisites/analyze", data=data, files={"paper": ("p.pdf", content, "application/pdf")}).json()


def test_diagnostics_are_only_returned_when_asked_for():
    assert "diagnostics" not in _post(SAMPLE.read_bytes())
    asked = _post(SAMPLE.read_bytes(), diagnostics="true")
    assert asked["status"] == "success" and asked["diagnostics"]["statistics"]["concepts"] == 5
    assert asked["diagnostics"]["stage_seconds"] and asked["diagnostics"]["failed_stage"] is None


def test_diagnostics_accompany_a_failed_analysis_without_the_server_path():
    failed = _post(b"not a pdf", diagnostics="true")
    assert failed["status"] == "failure" and "diagnostics" in failed
    assert failed["diagnostics"]["failed_stage"] == "ingestion"  # names where it failed
    assert tempfile.gettempdir() not in str(failed)  # the server's temporary copy never leaks
