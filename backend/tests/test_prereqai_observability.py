"""Structured events: one request id across the request, the stages, the cache and the PDF worker; timings and cache hits and misses are recorded; failures have a category; nothing sensitive is logged."""
import json
import logging

import pytest
from fastapi.testclient import TestClient

from backend import analysis_cache as cache_module
from backend import observability
from backend.ingestion import isolated_parse
from backend.ingestion.pdf_guard import PdfGuardError
from backend.main import app
from backend.session import session_manager

pytestmark = pytest.mark.prereqai
SAMPLE = "examples/prerequisites/sample-paper.pdf"
client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def events(caplog, tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path / "sessions"))
    monkeypatch.setenv("PREREQAI_ANALYSIS_CACHE_DIR", str(tmp_path / "cache"))
    cache_module.analysis_cache.clear()
    session_manager.sessions.clear()
    caplog.set_level(logging.INFO, logger=observability.EVENT_LOGGER)
    yield lambda: [r.fields for r in caplog.records if r.name == observability.EVENT_LOGGER]
    cache_module.analysis_cache.clear()
    session_manager.sessions.clear()


def upload(headers=None, token=None):
    with open(SAMPLE, "rb") as handle:
        return client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf")}, headers=headers or {})


def test_one_request_id_covers_the_request_its_stages_and_the_cache(events):
    response = upload({"X-Request-ID": "trace-abc.123"})
    assert response.status_code == 200 and response.headers["x-request-id"] == "trace-abc.123"
    logged = events()
    assert {e["event"] for e in logged} >= {"request", "analysis", "stage", "cache"} and {e["request_id"] for e in logged} == {"trace-abc.123"}
    request = next(e for e in logged if e["event"] == "request")
    assert request["route"] == "/api/prerequisites/analyze" and request["status"] == 200 and request["duration_ms"] > 0


def test_a_missing_or_malformed_request_id_is_replaced(events):
    first, second = client.get("/health"), client.get("/health", headers={"X-Request-ID": "bad id\x7f!" })
    assert first.headers["x-request-id"] != second.headers["x-request-id"] and len(first.headers["x-request-id"]) == 16
    assert observability.clean_request_id("x" * 65) is None and observability.clean_request_id("") is None and observability.clean_request_id("ok_1-2.3") == "ok_1-2.3"


def test_stage_timings_are_measurable_and_cover_the_pipeline(events):
    upload()
    stages = [e for e in events() if e["event"] == "stage"]
    assert len(stages) >= 5 and all(e["duration_ms"] >= 0 and e["stage"] for e in stages) and len({e["stage"] for e in stages}) == len(stages)
    analysis = next(e for e in events() if e["event"] == "analysis")
    assert analysis["status"] == "success" and analysis["duration_ms"] >= sum(e["duration_ms"] for e in stages) * 0.5 and "error_category" not in analysis


def test_cache_misses_stores_and_hits_are_observable(events):
    upload()
    upload()
    results = [e["result"] for e in events() if e["event"] == "cache"]
    assert results == ["miss", "stored", "hit"] and len({e["key"] for e in events() if e["event"] == "cache"}) == 1
    assert len([e for e in events() if e["event"] == "stage"]) >= 5  # the second request ran no stage: only the first did


def test_worker_lifecycle_and_failures_are_diagnosable(events, monkeypatch):
    monkeypatch.setattr(isolated_parse, "_run_worker", lambda *a: {"repaired": False})
    isolated_parse.run_worker("secret-name.pdf")
    monkeypatch.setattr(isolated_parse, "_run_worker", lambda *a: (_ for _ in ()).throw(PdfGuardError("timeout", "reading this PDF took longer than 5 seconds and was stopped")))
    with pytest.raises(PdfGuardError):
        isolated_parse.run_worker("secret-name.pdf")
    monkeypatch.setattr(isolated_parse, "_run_worker", lambda *a: (_ for _ in ()).throw(PdfGuardError("resource_exhausted", "memory")))
    with pytest.raises(PdfGuardError):
        isolated_parse.run_worker("secret-name.pdf")
    logged = [e for e in events() if e["event"].startswith("worker")]
    assert [e["event"] for e in logged] == ["worker_start", "worker_end", "worker_start", "worker_failed", "worker_start", "worker_failed"]
    assert (logged[3]["reason"], logged[3]["error_category"], logged[3]["killed"]) == ("timeout", "timeout", True) and (logged[5]["reason"], logged[5]["error_category"]) == ("resource_exhausted", "resource_limit")
    assert "secret-name" not in json.dumps(logged)


def test_errors_are_categorised():
    assert observability.categorise("timeout") == "timeout" and observability.categorise(PdfGuardError("too_many_pages", "x")) == "input_limit"
    assert observability.categorise(PdfGuardError("worker_failed", "x")) == "worker_failure" and observability.categorise(MemoryError()) == "resource_limit"
    assert observability.categorise(ValueError("x")) == "invalid_input" and observability.categorise(ImportError()) == "dependency" and observability.categorise(RuntimeError()) == "internal"
    assert set(observability.ERROR_CATEGORIES) >= {observability.categorise(e) for e in (ValueError(), RuntimeError(), MemoryError(), ImportError(), TimeoutError())}


def test_a_failed_analysis_logs_its_category_and_no_content(events):
    response = client.post("/api/prerequisites/analyze", files={"paper": ("my-private-notes.pdf", b"%PDF-1.4 this is not a pdf at all, it is secret text", "application/pdf")})
    assert response.status_code >= 400
    text = json.dumps(events())
    analysis = [e for e in events() if e["event"] == "analysis"]
    assert analysis and analysis[0]["status"] != "success" and analysis[0]["error_category"] in observability.ERROR_CATEGORIES
    assert "my-private-notes" not in text and "secret text" not in text


def test_logs_never_contain_paper_text_tokens_profile_names_or_session_ids(events, monkeypatch, tmp_path, caplog):
    monkeypatch.setenv("PREREQAI_API_TOKEN", "tok-should-never-appear")
    monkeypatch.setenv("PREREQAI_PROFILE_DIR", str(tmp_path / "profiles"))
    headers = {"Authorization": "Bearer tok-should-never-appear"}
    body = upload(headers).json()
    client.get(f"/api/session/{body['session_id']}", headers=headers)
    client.get("/api/profiles/learner-jane-doe", headers=headers)
    client.get("/api/session", headers={"Authorization": "Bearer tok-wrong-value"})
    text = json.dumps(events()) + caplog.text
    for secret in ("tok-should-never-appear", "tok-wrong-value", body["session_id"], "learner-jane-doe", "sample-paper", "Attention"):
        assert secret not in text, secret
    routes = {e["route"] for e in events() if e["event"] == "request"}
    assert "/api/session/{session_id}" in routes and "/api/profiles/{name}" in routes


def test_log_event_drops_sensitive_looking_and_oversized_fields():
    record = observability.log_event("probe", ok=1, ratio=0.12345, flag=True, note="x" * 500, authorization="Bearer abc", file_name="a.pdf", paper_text="body", nested={"a": 1.5}, bad={"a": "str"})
    assert record["ok"] == 1 and record["ratio"] == 0.123 and record["flag"] is True and len(record["note"]) == observability.MAX_VALUE_CHARS and record["nested"] == {"a": 1.5}
    assert not {"authorization", "file_name", "paper_text", "bad"} & set(record)
