"""The browser interface is served by the app, stays out of the API schema, and reads only fields the real API returns."""
import re

import pytest
from fastapi.testclient import TestClient

from backend.main import app

pytestmark = pytest.mark.prereqai

client = TestClient(app)
SAMPLE = "examples/prerequisites/sample-paper.pdf"


def _page():
    return client.get("/").text


def test_the_page_is_served_as_html_with_the_form_and_result_areas():
    response = client.get("/")
    assert response.status_code == 200 and response.headers["content-type"].startswith("text/html")
    for element in ('id="form"', 'id="paper"', 'id="source"', 'id="known"', 'id="submit"', 'id="status"', 'id="results"',
                    'name="viewport"', "/api/prerequisites/analyze"):
        assert element in _page()


def test_the_page_is_not_part_of_the_openapi_contract_and_the_api_is_unchanged():
    assert "/" not in client.get("/openapi.json").json()["paths"]
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/no-such-page").status_code == 404


def test_the_page_loads_nothing_from_other_sites_and_never_writes_untrusted_text_as_html():
    page = _page()
    assert not re.search(r'(src|href)="https?://', page) and "innerHTML" not in page and "insertAdjacentHTML" not in page


def test_every_report_field_the_page_reads_exists_in_a_real_analysis():
    with open(SAMPLE, "rb") as handle:
        body = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf")}).json()
    report = body["report"]
    assert body["status"] == "success" and isinstance(body["warnings"], list)
    for key in ("paper", "concept_evidence", "missing_prerequisites", "learning_plan", "learning_resources", "paper_difficulty", "study_time", "readiness"):
        assert key in report and f"report.{key}" in _page()
    assert {"title", "author", "pages"} <= set(report["paper"])
    assert {"concept", "domain", "occurrences", "mentioned_once"} <= set(report["concept_evidence"][0])
    assert {"concept", "satisfied", "reason"} <= set(report["missing_prerequisites"][0])
    assert {"step", "concept", "estimated_hours"} <= set(report["learning_plan"][0])
    assert {"concept", "title", "url"} <= set(report["learning_resources"][0])
    assert {"total_hours", "recommended_days"} <= set(report["study_time"]) and {"status", "progress_percent"} <= set(report["readiness"])


def test_the_failure_envelope_the_page_shows_has_detail_and_hint():
    body = client.post("/api/prerequisites/analyze", data={"source": "not a paper"}).json()
    assert body["status"] == "failure" and body["detail"] and body["hint"]
    assert "body.detail" in _page() and "body.hint" in _page()
