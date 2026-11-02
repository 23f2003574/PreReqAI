"""/openapi.json describes the failure bodies the endpoints really return: every failing request below answers with a status
its operation declares, the declared schema is the failure envelope (not FastAPI's validation-error shape), and the real body
validates against it."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api.workflow_result import FailureEnvelope
from backend.main import app

pytestmark = pytest.mark.prereqai

PAPER = (Path(__file__).resolve().parents[2] / "examples" / "prerequisites" / "sample-paper.pdf").read_bytes()
client = TestClient(app)
SPEC = client.get("/openapi.json").json()


def _session():
    return client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", PAPER, "application/pdf")}).json()["session_id"]


def _cases():
    sid = "live"  # replaced by a session created inside the test (sessions made at collection time may be cleared by other tests)
    pdf = ("p.pdf", PAPER, "application/pdf")
    return [
        ("post", "/api/prerequisites/analyze", {"files": {"paper": ("p.pdf", b"not a pdf", "application/pdf")}}, 400),
        ("post", "/api/prerequisites/analyze", {}, 422),
        ("post", "/api/prerequisites/analyze", {"files": {"paper": pdf}, "data": {"source": "arXiv:1706.03762"}}, 422),
        ("get", "/api/session/{session_id}", {"path": "missing"}, 404),
        ("get", "/api/session/{session_id}/plan", {"path": "missing"}, 404),
        ("post", "/api/session/{session_id}/question", {"path": sid, "json": {"question": ""}}, 422),
        ("post", "/api/session/{session_id}/question", {"path": "missing", "json": {"question": "hi"}}, 404),
        ("post", "/api/prerequisites/sessions/{session_id}/studied", {"path": sid, "params": {"concept": "nonsense"}}, 422),
    ]


@pytest.mark.parametrize("method, template, kwargs, expected", _cases())
def test_real_failures_match_the_declared_openapi_response(method, template, kwargs, expected):
    kwargs = dict(kwargs)
    session_id = kwargs.pop("path", "")
    url = template.format(session_id=_session() if session_id == "live" else session_id)
    response = getattr(client, method)(url, **kwargs)
    assert response.status_code == expected

    declared = SPEC["paths"][template][method]["responses"]
    assert str(expected) in declared
    schema = declared[str(expected)]["content"]["application/json"]["schema"]
    assert schema["$ref"].endswith("/FailureEnvelope")
    FailureEnvelope.model_validate(response.json())


def test_the_analysis_limit_statuses_are_declared_on_analyze_only():
    analyze = SPEC["paths"]["/api/prerequisites/analyze"]["post"]["responses"]
    assert {"400", "409", "413", "504"} <= set(analyze)
    assert "413" not in SPEC["paths"]["/api/session/{session_id}"]["get"]["responses"]


def test_the_success_responses_and_health_are_untouched():
    assert set(SPEC["paths"]["/health"]["get"]["responses"]) == {"200"}
