"""The whole PDF reading (layout, figures, tables, OCR) happens in a worker process under limits; the server decodes its result and never opens the upload."""
import os
import subprocess
import sys
import time

import pytest

from backend.ingestion import isolated_parse
from backend.ingestion.pdf_guard import PdfGuardError

pytestmark = pytest.mark.prereqai
SAMPLE = "examples/prerequisites/sample-paper.pdf"


@pytest.fixture(autouse=True)
def _worker_mode(monkeypatch):
    monkeypatch.delenv("PREREQAI_PARSE_INPROCESS", raising=False)  # the suite's default is in-process; these tests are about the worker
    token = isolated_parse.ISOLATED.set(True)
    yield
    isolated_parse.ISOLATED.reset(token)


def test_the_worker_result_equals_the_in_process_reading():
    from backend.ingestion import PDFIngestionEngine

    result = isolated_parse.run_worker(SAMPLE)
    direct = PDFIngestionEngine().ingest(SAMPLE)
    assert [p.text for p in result["document"].pages] == [p.text for p in direct.pages] and result["document"].metadata == direct.metadata
    assert result["limits_applied"].get("cpu") in (True, False) and result["repaired"] is False


def test_the_pipeline_never_opens_the_upload_in_the_server(monkeypatch):
    import pdfplumber
    import pymupdf

    def forbidden(*args, **kwargs):
        raise AssertionError("the server opened the PDF itself")

    monkeypatch.setattr(pymupdf, "open", forbidden)
    monkeypatch.setattr(pdfplumber, "open", forbidden)
    monkeypatch.setattr("backend.ingestion.pdf_ingestion_engine.fitz.open", forbidden)
    stages = isolated_parse.IsolatedStages(runner=lambda path, ocr: {"document": "D", "figures": ["F"], "tables": ["T"], "repaired": False})
    paper = type("P", (), {})()
    assert stages.ingest(SAMPLE) == "D" and stages.figures(SAMPLE, paper).figures == ["F"] and stages.tables(SAMPLE, paper).tables == ["T"]


def test_a_page_too_large_to_render_is_refused_in_the_worker(tmp_path, monkeypatch):
    from reportlab.pdfgen import canvas

    path = tmp_path / "huge.pdf"
    pdf = canvas.Canvas(str(path), pagesize=(14000, 14000))
    pdf.drawString(100, 100, "text")
    pdf.save()
    with pytest.raises(PdfGuardError) as info:
        isolated_parse.run_worker(str(path))
    assert info.value.kind == "page_too_large" and "million pixels" in info.value.message


def test_a_stalled_worker_is_killed_with_its_children(tmp_path):
    marker = tmp_path / "child.pid"
    script = f"import subprocess,sys,time; c=subprocess.Popen(['sleep','60']); open({str(marker)!r},'w').write(str(c.pid)); time.sleep(60)"
    started = time.time()
    with pytest.raises(PdfGuardError) as info:
        isolated_parse.run_worker(SAMPLE, command=[sys.executable, "-c", script], seconds=2)
    assert info.value.kind == "timeout" and time.time() - started < 15
    pid = int(marker.read_text())
    time.sleep(0.5)
    with pytest.raises(OSError):
        os.kill(pid, 0)  # no child survived


def test_a_worker_that_dies_or_is_not_a_pdf_is_a_structured_failure(tmp_path):
    with pytest.raises(PdfGuardError) as died:
        isolated_parse.run_worker(SAMPLE, command=[sys.executable, "-c", "import os; os._exit(9)"])
    assert died.value.kind == "worker_failed"
    junk = tmp_path / "junk.pdf"
    junk.write_bytes(b"not a pdf at all")
    with pytest.raises(PdfGuardError) as bad:
        isolated_parse.run_worker(str(junk))
    assert bad.value.kind == "worker_failed"


def test_the_upload_route_analyses_through_the_worker(monkeypatch):
    from fastapi.testclient import TestClient

    from backend.main import app

    started = []
    real = subprocess.Popen
    monkeypatch.setattr(isolated_parse.subprocess, "Popen", lambda command, *a, **k: started.append(list(command)) or real(command, *a, **k))
    with open(SAMPLE, "rb") as handle:
        body = TestClient(app).post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf")}).json()
    assert body["status"] == "success" and any("backend.ingestion.isolated_parse" in command for command in started)  # the whole reading ran in the worker process
