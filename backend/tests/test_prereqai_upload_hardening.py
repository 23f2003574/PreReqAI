"""An upload is checked as a PDF by its own bytes before any worker starts, and at most PREREQAI_MAX_CONCURRENT_ANALYSES analyses run at once (the others get 503 with Retry-After); temp files never outlive a request."""
import logging
import tempfile
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import analysis_slots, observability
from backend.api import prerequisite_routes
from backend.ingestion import isolated_parse
from backend.main import app

pytestmark = pytest.mark.prereqai
SAMPLE = Path("examples/prerequisites/sample-paper.pdf")
client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def events(caplog):
    caplog.set_level(logging.INFO, logger=observability.EVENT_LOGGER)
    return lambda: [r.fields["event"] for r in caplog.records if r.name == observability.EVENT_LOGGER]


@pytest.fixture(autouse=True)
def worker_mode(monkeypatch):
    monkeypatch.delenv("PREREQAI_PARSE_INPROCESS", raising=False)  # the suite reads PDFs in-process; a server reads them in the worker, which is what is under test here


def post(data, content_type="application/pdf", name="paper.pdf"):
    return client.post("/api/prerequisites/analyze", files={"paper": (name, data, content_type)})


@pytest.mark.parametrize("data", [b"hello, this is plain text and not a pdf at all", b"", b"<html><body>" + b" " * 2000 + b"%PDF- far beyond the first 1024 bytes</body>", bytes(range(256)) * 8, b"PK\x03\x04" + b"0" * 200])
def test_a_file_that_is_not_a_pdf_is_refused_before_any_worker_starts(data, events, tmp_path, monkeypatch):
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    response = post(data)
    body = response.json()
    assert response.status_code == 400 and body["status"] == "failure" and body["stage"] == "analysis" and "could not be read as a PDF" in body["detail"] and body["error"]["type"] == "PdfGuardError"
    assert "worker_start" not in events() and "worker_refused" in events()  # no worker process was started
    assert list(tmp_path.iterdir()) == []  # the temporary copy is gone


def test_the_name_and_content_type_do_not_make_a_file_a_pdf():
    assert post(b"just words", "application/pdf", "real.pdf").status_code == 400
    assert post(b"just words", "text/plain", "notes.txt").status_code == 400


def test_a_real_pdf_with_a_short_preamble_is_accepted_by_the_check_and_the_sample_still_analyses(tmp_path):
    assert isolated_parse.looks_like_pdf(SAMPLE)
    prefixed = tmp_path / "p.pdf"
    prefixed.write_bytes(b"\n" * 100 + SAMPLE.read_bytes())
    assert isolated_parse.looks_like_pdf(prefixed)
    late = tmp_path / "late.pdf"
    late.write_bytes(b"\n" * 2000 + SAMPLE.read_bytes())
    assert not isolated_parse.looks_like_pdf(late) and isolated_parse.looks_like_pdf(tmp_path / "missing.pdf")  # a file that cannot be opened is left to the worker to report
    response = post(SAMPLE.read_bytes())
    assert response.status_code == 200 and response.json()["status"] == "success"


def test_a_damaged_pdf_fails_safely_and_leaves_nothing_behind(tmp_path, monkeypatch):
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    response = post(b"%PDF-1.4\n1 0 obj << /Type /Catalog >> endobj\n" + b"garbage" * 50)
    assert response.status_code >= 400 and response.json()["status"] != "success"
    assert list(tmp_path.iterdir()) == []


def slow_analysis(counter):
    def fake(path, **kwargs):
        with counter["lock"]:
            counter["now"] += 1
            counter["max"] = max(counter["max"], counter["now"])
        time.sleep(0.4)
        with counter["lock"]:
            counter["now"] -= 1
        return {"status": "failure", "stage": "analysis", "detail": "stub", "error": None, "hint": None, "warnings": []}
    return fake


def test_concurrent_analyses_never_exceed_the_limit_and_the_rest_get_503_with_retry_after(monkeypatch, events):
    monkeypatch.setenv(analysis_slots.SLOTS_ENV, "2")
    counter = {"lock": threading.Lock(), "now": 0, "max": 0}
    monkeypatch.setattr(prerequisite_routes.platform, "analyze", slow_analysis(counter))
    monkeypatch.setattr(prerequisite_routes, "_guard_upload", lambda path: None)
    responses = []
    threads = [threading.Thread(target=lambda: responses.append(post(SAMPLE.read_bytes()))) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    refused = [r for r in responses if r.status_code == 503]
    assert counter["max"] <= 2 and counter["max"] >= 1 and len(responses) == 8 and 1 <= len(refused) <= 6
    assert all(r.headers["retry-after"] == "5" and r.json()["status"] == "failure" and "cannot take another" in r.json()["detail"] for r in refused)
    assert "overloaded" in events() and analysis_slots.active() == 0


def test_every_slot_is_released_after_success_failure_and_an_exception(monkeypatch):
    monkeypatch.setenv(analysis_slots.SLOTS_ENV, "1")
    assert post(b"not a pdf").status_code == 400 and analysis_slots.active() == 0
    assert post(SAMPLE.read_bytes()).status_code == 200 and analysis_slots.active() == 0
    monkeypatch.setattr(prerequisite_routes.platform, "analyze", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    assert post(SAMPLE.read_bytes()).status_code >= 500 and analysis_slots.active() == 0
    monkeypatch.undo()
    monkeypatch.setenv(analysis_slots.SLOTS_ENV, "1")
    assert post(SAMPLE.read_bytes()).status_code == 200  # the one slot is free again


def test_the_limit_setting_is_forgiving():
    import os
    default = analysis_slots.limit()
    assert 1 <= default <= 4
    for value, expected in (("3", 3), (" 2 ", 2), ("0", default), ("-1", default), ("many", default), ("", default), ("2.5", default)):
        os.environ[analysis_slots.SLOTS_ENV] = value
        try:
            assert analysis_slots.limit() == expected, value
        finally:
            del os.environ[analysis_slots.SLOTS_ENV]
    assert analysis_slots.try_acquire() and analysis_slots.active() == 1
    analysis_slots.release()
    analysis_slots.release()  # an extra release never goes below zero
    assert analysis_slots.active() == 0
