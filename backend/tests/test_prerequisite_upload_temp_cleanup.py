"""POST /api/prerequisites/analyze writes the upload to a temp file; that file is
removed after the analysis, and also when copying the upload itself fails."""
import tempfile

from fastapi.testclient import TestClient

from backend.api import prerequisite_routes
from backend.main import app

client = TestClient(app, raise_server_exceptions=False)


class _Interrupted:
    """A temp file whose write fails after storing part of the upload (the client dropped mid-copy)."""

    def __init__(self, temp, write):
        self._temp, self.write = temp, write
        self.name = temp.name

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return self._temp.__exit__(*exc)


def _upload():
    return client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", b"not a pdf", "application/pdf")})


def test_temp_file_is_removed_after_an_analysis(tmp_path, monkeypatch):
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))

    assert _upload().status_code == 400
    assert list(tmp_path.iterdir()) == []


def test_temp_file_is_removed_when_copying_the_upload_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))

    real_temp_file = tempfile.NamedTemporaryFile

    def interrupted_temp_file(*args, **kwargs):
        temp = real_temp_file(*args, **kwargs)

        def write(chunk):
            temp.__class__.write(temp, b"%PDF-partial")
            raise ConnectionResetError("client went away mid-upload")

        return _Interrupted(temp, write)

    monkeypatch.setattr(prerequisite_routes.tempfile, "NamedTemporaryFile", interrupted_temp_file)

    assert _upload().status_code == 500
    assert list(tmp_path.iterdir()) == []  # previously the partial upload stayed on disk
