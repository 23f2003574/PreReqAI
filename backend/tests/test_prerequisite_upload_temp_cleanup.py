"""POST /api/prerequisites/analyze writes the upload to a temp file; that file is
removed after the analysis, and also when copying the upload itself fails."""
import tempfile

from fastapi.testclient import TestClient

from backend.api import prerequisite_routes
from backend.main import app

client = TestClient(app, raise_server_exceptions=False)


def _upload():
    return client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", b"not a pdf", "application/pdf")})


def test_temp_file_is_removed_after_an_analysis(tmp_path, monkeypatch):
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))

    assert _upload().status_code == 400
    assert list(tmp_path.iterdir()) == []


def test_temp_file_is_removed_when_copying_the_upload_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))

    def interrupted(source, target):
        target.write(b"%PDF-partial")
        raise ConnectionResetError("client went away mid-upload")

    monkeypatch.setattr(prerequisite_routes.shutil, "copyfileobj", interrupted)

    assert _upload().status_code == 500
    assert list(tmp_path.iterdir()) == []  # previously the partial upload stayed on disk
