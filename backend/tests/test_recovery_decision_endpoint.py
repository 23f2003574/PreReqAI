from fastapi.testclient import (
    TestClient,
)

from backend.agent_task_recovery_execution_precondition_snapshots import (
    AgentTaskRecoveryExecutionDecisionLifecycleResult,
    IMPACT_LIFECYCLE_BLOCKED,
    IMPACT_LIFECYCLE_REMEDIATED,
    LIFECYCLE_VERIFICATION_VALID,
    InvalidAgentTaskRecoveryExecutionDecisionLifecycleFacadeError,
)

import backend.api.recovery_decision_routes as recovery_decision_routes
from backend.main import app


client = TestClient(app)


def _result(**overrides):
    fields = dict(
        task_id="task-1",
        authoritative_decision_id="d2",
        decision_lineage_status="valid",
        affected_artifacts=("authorization:d1",),
        remediation_operation_id="op-1",
        reconciliation_operation_id=None,
        blocking_conditions=(),
        verification_status=LIFECYCLE_VERIFICATION_VALID,
        overall_status=IMPACT_LIFECYCLE_REMEDIATED,
        diagnostics=(),
    )
    fields.update(overrides)
    return AgentTaskRecoveryExecutionDecisionLifecycleResult(**fields)


class _FakeFacade:
    def __init__(self, result=None, error=None):
        self._result, self._error = result, error

    def evaluate(self, task_id):
        if self._error is not None:
            raise self._error
        return self._result


def _use(monkeypatch, facade):
    monkeypatch.setattr(recovery_decision_routes, "facade", facade)


def test_successful_evaluation_returns_the_consolidated_result(monkeypatch):
    _use(monkeypatch, _FakeFacade(_result()))

    response = client.post("/api/tasks/task-1/recovery-decision/evaluate")

    assert response.status_code == 200
    assert response.json() == _result().to_dict()


def test_response_structure_is_deterministic_across_repeated_calls(monkeypatch):
    _use(monkeypatch, _FakeFacade(_result()))

    first = client.post("/api/tasks/task-1/recovery-decision/evaluate")
    second = client.post("/api/tasks/task-1/recovery-decision/evaluate")

    assert first.json() == second.json()
    assert list(first.json().keys()) == list(second.json().keys())


def test_blocked_lifecycle_is_a_200_with_the_blocked_outcome_in_the_body(monkeypatch):
    _use(monkeypatch, _FakeFacade(_result(
        overall_status=IMPACT_LIFECYCLE_BLOCKED,
        blocking_conditions=("authorization:d1", "preflight:d1"),
    )))

    response = client.post("/api/tasks/task-1/recovery-decision/evaluate")

    assert response.status_code == 200
    body = response.json()
    assert body["overall_status"] == IMPACT_LIFECYCLE_BLOCKED
    assert body["blocking_conditions"] == ["authorization:d1", "preflight:d1"]


def test_invalid_task_id_is_a_422_not_an_internal_failure(monkeypatch):
    _use(monkeypatch, _FakeFacade(error=InvalidAgentTaskRecoveryExecutionDecisionLifecycleFacadeError(
        "task_id is required and must be a non-empty string"
    )))

    response = client.post("/api/tasks/%20/recovery-decision/evaluate")

    assert response.status_code == 422
    assert "task_id" in response.json()["detail"]


def test_missing_task_evaluates_with_the_real_wired_facade_and_stays_a_200(monkeypatch):
    """A well-formed task_id with no recorded decisions is not an HTTP
    error -- it's a legitimate, terminal lifecycle outcome (unresolved),
    reported in the body the same way a blocked one is."""
    response = client.post("/api/tasks/never-seen-task/recovery-decision/evaluate")

    assert response.status_code == 200
    body = response.json()
    assert body["overall_status"] == "unresolved"
    assert body["authoritative_decision_id"] is None


def test_internal_service_failure_is_a_500_distinguishable_from_a_blocked_lifecycle(monkeypatch):
    _use(monkeypatch, _FakeFacade(error=RuntimeError("store unavailable")))

    response = client.post("/api/tasks/task-1/recovery-decision/evaluate")

    assert response.status_code == 500
    detail = response.json()["detail"]
    assert "store unavailable" not in detail
    assert "Traceback" not in detail


def test_endpoint_is_registered_in_the_generated_openapi_schema():
    schema = client.get("/openapi.json").json()

    assert "/api/tasks/{task_id}/recovery-decision/evaluate" in schema["paths"]
    assert "post" in schema["paths"]["/api/tasks/{task_id}/recovery-decision/evaluate"]
