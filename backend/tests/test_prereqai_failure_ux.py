"""User-facing failure paths share one shape: the CLI names what failed, why,
and what to do next; the session API answers failures with the workflow
failure envelope instead of a bare 500 or an accepted blank question."""
from fastapi.testclient import TestClient

from backend.api import session_routes
from backend.cli import EXIT_FAILURE, main
from backend.main import app
from backend.session import session_manager

client = TestClient(app, raise_server_exceptions=False)

class _Broken:
    def evaluate(self, task_id):
        raise RuntimeError("store unavailable")

    check = evaluate

def test_cli_unexpected_failures_name_the_operation_reason_and_next_step(capsys):
    for command, kwargs, verb in (("evaluate", {"facade": _Broken()}, "evaluate"),
                                  ("diagnose", {"health_service": _Broken()}, "diagnose"),
                                  ("readiness", {"readiness_service": _Broken()}, "compute readiness for")):
        assert main(["recovery-decision", command, "task-1"], **kwargs) == EXIT_FAILURE
        err = capsys.readouterr().err
        assert err.startswith(f"error: failed to {verb} the recovery execution decision lifecycle: "
                              "RuntimeError: store unavailable\n"), err
        assert "hint: run `recovery-decision readiness`" in err and "Traceback" not in err

def test_blank_question_is_rejected_with_the_failure_envelope(monkeypatch):
    monkeypatch.setattr(session_manager, "get", lambda session_id: object())

    response = client.post("/api/session/s-1/question", json={"question": "   "})

    body = response.json()
    assert response.status_code == 422 and body["status"] == "failure" and body["stage"] == "question"
    assert body["detail"] == "Question must be a non-empty string" and body["hint"]

def test_answer_crash_returns_the_failure_envelope_not_a_bare_500(monkeypatch):
    class _Session:
        paper = None

    def _boom(**_):
        raise RuntimeError("tutor offline")

    monkeypatch.setattr(session_manager, "get", lambda session_id: _Session())
    monkeypatch.setattr(session_routes.pipeline, "answer", _boom)

    response = client.post("/api/session/s-1/question", json={"question": "What is attention?"})

    body = response.json()
    assert response.status_code == 500 and body["status"] == "failure" and body["stage"] == "question"
    assert body["detail"] == "Failed to answer the question" and body["hint"]
    assert body["error"] == {"type": "RuntimeError", "message": "tutor offline"}


def test_malformed_requests_get_the_failure_envelope_naming_the_bad_field():
    cases = (
        (client.post("/api/prerequisites/analyze"), "Invalid request: paper: Field required"),
        (client.post("/api/session/s-1/question", json={}), "Invalid request: question: Field required"),
        (client.post("/api/session/s-1/question", json={"question": "q", "mode": "eli5"}),
         "Invalid request: mode: Input should be 'intuition'"),
    )
    for response, detail in cases:
        body = response.json()
        assert response.status_code == 422 and body["status"] == "failure" and body["stage"] == "input"
        assert body["detail"].startswith(detail) and body["hint"] and body["warnings"] == []
