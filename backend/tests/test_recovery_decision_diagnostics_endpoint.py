from fastapi.testclient import (
    TestClient,
)

from backend.agent_task_recovery_execution_precondition_snapshots import (
    AgentTaskRecoveryExecutionDecisionLifecycleDependencyDiagnostic,
    AgentTaskRecoveryExecutionDecisionLifecycleHealthCheck,
    AgentTaskRecoveryExecutionDecisionLifecycleHealthResult,
    DEPENDENCY_ORDER,
    HEALTH_BLOCKED,
    HEALTH_DEGRADED,
    HEALTH_HEALTHY,
    HEALTH_UNAVAILABLE,
    InvalidAgentTaskRecoveryExecutionDecisionLifecycleHealthError,
)

import backend.api.recovery_decision_routes as recovery_decision_routes
from backend.main import app


client = TestClient(app)


def _dependency_diagnostics(status=HEALTH_HEALTHY, failure_reason=None, blocking=False):
    return tuple(
        AgentTaskRecoveryExecutionDecisionLifecycleDependencyDiagnostic(
            dependency=name,
            status=status if name == DEPENDENCY_ORDER[0] else HEALTH_HEALTHY,
            failure_reason=failure_reason if name == DEPENDENCY_ORDER[0] else None,
            last_verified_state="ok",
            blocking=blocking if name == DEPENDENCY_ORDER[0] else False,
        )
        for name in DEPENDENCY_ORDER
    )


def _result(**overrides):
    fields = dict(
        task_id="task-1",
        status=HEALTH_HEALTHY,
        checks=(AgentTaskRecoveryExecutionDecisionLifecycleHealthCheck("decision_store_availability", True, "ok"),),
        issues=(),
        authoritative_decision_id="d1",
        latest_lifecycle_result_id="result-1",
        dependency_diagnostics=_dependency_diagnostics(),
    )
    fields.update(overrides)
    return AgentTaskRecoveryExecutionDecisionLifecycleHealthResult(**fields)


class _FakeHealthService:
    def __init__(self, result=None, error=None):
        self._result, self._error = result, error

    def check(self, task_id):
        if self._error is not None:
            raise self._error
        return self._result


def _use(monkeypatch, health_service):
    monkeypatch.setattr(recovery_decision_routes, "health_service", health_service)


def test_healthy_state_returns_200_with_the_full_result(monkeypatch):
    _use(monkeypatch, _FakeHealthService(_result()))

    response = client.get("/api/tasks/task-1/recovery-decision/diagnostics")

    assert response.status_code == 200
    body = response.json()
    expected = _result().to_dict()
    body.pop("checked_at"), expected.pop("checked_at")
    assert body == expected
    assert body["status"] == HEALTH_HEALTHY
    assert len(body["dependency_diagnostics"]) == len(DEPENDENCY_ORDER)


def test_degraded_state_returns_200_distinguishable_from_healthy(monkeypatch):
    _use(monkeypatch, _FakeHealthService(_result(
        status=HEALTH_DEGRADED,
        dependency_diagnostics=_dependency_diagnostics(
            status=HEALTH_DEGRADED, failure_reason="no persisted lifecycle result found for task_id",
        ),
    )))

    response = client.get("/api/tasks/task-1/recovery-decision/diagnostics")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == HEALTH_DEGRADED
    assert body["dependency_diagnostics"][0]["status"] == HEALTH_DEGRADED


def test_blocked_state_returns_200_with_the_blocking_dependency_marked(monkeypatch):
    _use(monkeypatch, _FakeHealthService(_result(
        status=HEALTH_BLOCKED,
        dependency_diagnostics=_dependency_diagnostics(
            status=HEALTH_BLOCKED, failure_reason="3 blocking artifact(s)", blocking=True,
        ),
    )))

    response = client.get("/api/tasks/task-1/recovery-decision/diagnostics")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == HEALTH_BLOCKED
    assert body["dependency_diagnostics"][0]["blocking"] is True


def test_unavailable_state_maps_to_503_but_keeps_the_full_structured_body(monkeypatch):
    """Infrastructure failure goes through this API's existing
    error-status convention (503), but -- unlike a raised exception --
    the full diagnostic body (which dependency, why) is preserved rather
    than collapsed into a bare {"detail": ...} string."""
    _use(monkeypatch, _FakeHealthService(_result(
        status=HEALTH_UNAVAILABLE,
        dependency_diagnostics=_dependency_diagnostics(
            status=HEALTH_UNAVAILABLE, failure_reason="RuntimeError: store down", blocking=True,
        ),
    )))

    response = client.get("/api/tasks/task-1/recovery-decision/diagnostics")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == HEALTH_UNAVAILABLE
    assert body["dependency_diagnostics"][0]["failure_reason"] == "RuntimeError: store down"


def test_missing_task_uses_the_real_wired_health_service_and_returns_200_blocked():
    """A well-formed task_id with no recorded decisions is not an HTTP
    error -- it's a legitimate, terminal diagnostic outcome (blocked)."""
    response = client.get("/api/tasks/never-seen-task/recovery-decision/diagnostics")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == HEALTH_BLOCKED
    assert body["authoritative_decision_id"] is None


def test_malformed_task_id_is_a_422_not_an_internal_or_infrastructure_failure(monkeypatch):
    _use(monkeypatch, _FakeHealthService(error=InvalidAgentTaskRecoveryExecutionDecisionLifecycleHealthError(
        "task_id is required and must be a non-empty string"
    )))

    response = client.get("/api/tasks/%20/recovery-decision/diagnostics")

    assert response.status_code == 422
    assert "task_id" in response.json()["detail"]


def test_internal_service_failure_is_a_500_without_a_stack_trace(monkeypatch):
    _use(monkeypatch, _FakeHealthService(error=RuntimeError("unexpected bug")))

    response = client.get("/api/tasks/task-1/recovery-decision/diagnostics")

    assert response.status_code == 500
    detail = response.json()["detail"]
    assert "unexpected bug" not in detail
    assert "Traceback" not in detail


def test_response_structure_is_deterministic_across_repeated_calls(monkeypatch):
    _use(monkeypatch, _FakeHealthService(_result()))

    first = client.get("/api/tasks/task-1/recovery-decision/diagnostics")
    second = client.get("/api/tasks/task-1/recovery-decision/diagnostics")

    assert first.json() == second.json()
    assert list(first.json().keys()) == list(second.json().keys())


def test_endpoint_is_registered_in_the_generated_openapi_schema():
    schema = client.get("/openapi.json").json()

    assert "/api/tasks/{task_id}/recovery-decision/diagnostics" in schema["paths"]
    assert "get" in schema["paths"]["/api/tasks/{task_id}/recovery-decision/diagnostics"]
