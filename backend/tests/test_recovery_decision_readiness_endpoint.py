from fastapi.testclient import (
    TestClient,
)

from backend.agent_task_recovery_execution_precondition_snapshots import (
    AgentTaskRecoveryExecutionDecisionLifecycleReadinessResult,
    HEALTH_HEALTHY,
    HEALTH_UNAVAILABLE,
    LINEAGE_INVALID,
    LINEAGE_NOT_APPLICABLE,
    READINESS_BLOCKED,
    READINESS_VERIFICATION_NOT_APPLICABLE,
    READY,
    InvalidAgentTaskRecoveryExecutionDecisionLifecycleReadinessError,
)

import backend.api.recovery_decision_routes as recovery_decision_routes
from backend.main import app


client = TestClient(app)


def _result(**overrides):
    fields = dict(
        status=READY,
        issues=(),
        configuration_status="valid",
        dependency_status=HEALTH_HEALTHY,
        decision_lineage_status=LINEAGE_NOT_APPLICABLE,
        verification_status=READINESS_VERIFICATION_NOT_APPLICABLE,
        blocking_conditions=(),
    )
    fields.update(overrides)
    return AgentTaskRecoveryExecutionDecisionLifecycleReadinessResult(**fields)


class _FakeReadinessService:
    def __init__(self, result=None, error=None):
        self._result, self._error = result, error
        self.calls = []

    def check(self, task_id=None):
        self.calls.append(task_id)
        if self._error is not None:
            raise self._error
        return self._result


def _use(monkeypatch, readiness_service):
    monkeypatch.setattr(recovery_decision_routes, "readiness_service", readiness_service)


def test_ready_environment_with_no_task_id_returns_200(monkeypatch):
    service = _FakeReadinessService(_result())
    _use(monkeypatch, service)

    response = client.get("/api/tasks/recovery-decision/readiness")

    assert response.status_code == 200
    assert response.json() == _result().to_dict()
    assert service.calls == [None]


def test_blocked_environment_still_returns_200_with_the_blocked_status(monkeypatch):
    _use(monkeypatch, _FakeReadinessService(_result(
        status=READINESS_BLOCKED,
        configuration_status="invalid",
        issues=("configuration: missing dependency staleness_service",),
    )))

    response = client.get("/api/tasks/recovery-decision/readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == READINESS_BLOCKED
    assert "missing dependency staleness_service" in body["issues"][0]


def test_task_scoped_readiness_passes_the_task_id_through(monkeypatch):
    service = _FakeReadinessService(_result(
        status=READINESS_BLOCKED, dependency_status=HEALTH_UNAVAILABLE, decision_lineage_status=LINEAGE_INVALID,
    ))
    _use(monkeypatch, service)

    response = client.get("/api/tasks/recovery-decision/readiness?task_id=task-1")

    assert response.status_code == 200
    assert service.calls == ["task-1"]
    assert response.json()["decision_lineage_status"] == LINEAGE_INVALID


def test_malformed_task_id_is_a_422(monkeypatch):
    _use(monkeypatch, _FakeReadinessService(error=InvalidAgentTaskRecoveryExecutionDecisionLifecycleReadinessError(
        "task_id must be a non-empty string when given"
    )))

    response = client.get("/api/tasks/recovery-decision/readiness?task_id=%20")

    assert response.status_code == 422
    assert "task_id" in response.json()["detail"]


def test_internal_service_failure_is_a_500_without_a_stack_trace(monkeypatch):
    _use(monkeypatch, _FakeReadinessService(error=RuntimeError("unexpected bug")))

    response = client.get("/api/tasks/recovery-decision/readiness")

    assert response.status_code == 500
    detail = response.json()["detail"]
    assert "unexpected bug" not in detail
    assert "Traceback" not in detail


def test_missing_task_uses_the_real_wired_readiness_service():
    response = client.get("/api/tasks/recovery-decision/readiness?task_id=never-seen-task")

    assert response.status_code == 200
    assert response.json()["status"] == READINESS_BLOCKED


def test_response_structure_is_deterministic_across_repeated_calls(monkeypatch):
    _use(monkeypatch, _FakeReadinessService(_result()))

    first = client.get("/api/tasks/recovery-decision/readiness")
    second = client.get("/api/tasks/recovery-decision/readiness")

    assert first.json() == second.json()
    assert list(first.json().keys()) == list(second.json().keys())


def test_endpoint_is_registered_in_the_generated_openapi_schema():
    schema = client.get("/openapi.json").json()

    assert "/api/tasks/recovery-decision/readiness" in schema["paths"]
    assert "get" in schema["paths"]["/api/tasks/recovery-decision/readiness"]
