import logging

import pytest
from fastapi.testclient import TestClient

from backend import observability
from backend.api.workflow_result import failure_body, timeout_body
from backend.ingestion.pdf_guard import PdfGuardError
from backend.main import app
from backend.platform.prereqai_platform import _outcome_category

pytestmark = pytest.mark.prereqai
client = TestClient(app, base_url="http://localhost")


@pytest.mark.parametrize("content", [b"", b"this is not a pdf at all", b"%PDF-1.4\n%%EOF"])
def test_corrupt_empty_and_non_pdf_uploads_are_invalid_input(content, caplog):
    with caplog.at_level(logging.INFO, logger="prereqai.events"):
        response = client.post("/api/prerequisites/analyze", files={"paper": ("x.pdf", content, "application/pdf")})
    assert response.status_code == 400
    analysis = [r.getMessage() for r in caplog.records if '"event": "analysis"' in r.getMessage()]
    assert analysis and '"error_category": "invalid_input"' in analysis[-1]


@pytest.mark.parametrize("kind,category", [("timeout", "timeout"), ("too_many_pages", "input_limit"), ("page_too_large", "input_limit"), ("resource_exhausted", "resource_limit"), ("worker_failed", "worker_failure")])
def test_guard_kinds_keep_their_categories(kind, category):
    assert _outcome_category(failure_body("analysis", "x", error=PdfGuardError(kind, "message that mentions nothing useful"))) == category


def test_the_category_comes_from_the_exception_not_from_its_wording():
    # wording that used to be read as a timeout or a worker failure: the structured category wins
    body = failure_body("analysis", "the worker took longer than expected", error=ValueError("bad value"))
    assert body.category == "invalid_input" and "category" not in body and _outcome_category(body) == "invalid_input"
    assert _outcome_category(timeout_body("analysis", "slow")) == "timeout"


def test_memory_wording_alone_does_not_make_a_limit_unless_the_precedence_says_so():
    assert _outcome_category({"status": "failure", "detail": "reading needed more than 2048 MB of memory", "error": {"type": "PdfGuardError"}}) == "resource_limit"
    assert _outcome_category({"status": "failure", "detail": "larger than the limit", "error": {"type": "ValueError"}}) == "invalid_input"


def test_a_declared_category_must_be_a_known_one():
    error = PdfGuardError("worker_failed", "m", category="made_up")
    assert observability.categorise(error) == "worker_failure"
