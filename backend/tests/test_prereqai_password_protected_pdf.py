"""A password-protected PDF is refused with a message that says so, not with the name of an internal exception."""
import pymupdf
import pytest

from backend.ingestion import isolated_parse
from backend.ingestion.pdf_guard import PdfGuardError

pytestmark = pytest.mark.prereqai
SAMPLE = "examples/prerequisites/sample-paper.pdf"


@pytest.fixture
def locked(tmp_path):
    path = tmp_path / "locked.pdf"
    with pymupdf.open(SAMPLE) as pdf:
        pdf.save(str(path), encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="secret", owner_pw="secret")
    return path


@pytest.fixture(autouse=True)
def _worker_mode(monkeypatch):
    monkeypatch.delenv("PREREQAI_PARSE_INPROCESS", raising=False)
    token = isolated_parse.ISOLATED.set(True)
    yield
    isolated_parse.ISOLATED.reset(token)


def test_the_worker_names_the_password_and_says_what_to_do(locked):
    with pytest.raises(PdfGuardError) as refused:
        isolated_parse.run_worker(str(locked))
    message = str(refused.value)
    assert "password-protected" in message and "ValueError" not in message and "upload" in message


def test_an_unprotected_pdf_is_still_read_and_a_damaged_file_keeps_its_own_message(tmp_path):
    assert isolated_parse.run_worker(SAMPLE)["document"].pages
    damaged = tmp_path / "damaged.pdf"
    damaged.write_bytes(b"%PDF-1.4\n" + b"\x00" * 200)
    with pytest.raises(PdfGuardError) as refused:
        isolated_parse.run_worker(str(damaged))
    assert "password" not in str(refused.value) and "could not be read as a PDF" in str(refused.value)


def test_the_upload_endpoint_answers_400_with_the_same_message(locked, monkeypatch, tmp_path):
    from fastapi.testclient import TestClient

    from backend.main import app

    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path / "sessions"))
    response = TestClient(app, base_url="http://localhost").post("/api/prerequisites/analyze", files={"paper": ("locked.pdf", locked.read_bytes(), "application/pdf")})
    assert response.status_code == 400 and "password-protected" in response.json()["detail"] and response.json()["status"] == "failure"
