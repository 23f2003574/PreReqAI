import dataclasses
from datetime import datetime, timezone

import pytest

from backend.agent_policy_engine import ALLOW
from backend.agent_task_event_analytics import RECOVERY_ACTION_RETRY, AgentTaskFailureRecoveryPlan
from backend.agent_task_lifecycle import PLANNED, READY as TASK_READY, RUNNING, LLMAgentTaskLifecycleService
from backend.agent_task_recovery_execution_precondition_snapshots import (
    InvalidAgentTaskRecoveryExecutionPreconditionSnapshotError,
    LLMAgentTaskRecoveryExecutionPreconditionSnapshotService,
)
from backend.agent_task_recovery_guardrails import (
    ACTIVE,
    AgentTaskRecoveryPreflightAuthorization,
    AgentTaskRecoveryPreflightResult,
    InMemoryAgentTaskRecoveryPreflightAuthorizationStore,
    LLMAgentTaskRecoveryPreflightAuthorizationService,
    LLMAgentTaskRecoveryPreflightStore,
)

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _definition(**overrides):
    definition = {"agent_id": "agent-1", "scope_id": "scope-1", "objective": "recover the task"}
    definition.update(overrides)
    return definition


def _task(lifecycle_service, **overrides):
    return lifecycle_service.create(_definition(**overrides))


def _advance_to(lifecycle_service, task, state):
    for target in (PLANNED, TASK_READY, RUNNING):
        if task.current_state == state:
            return task
        task = lifecycle_service.transition(task.task_id, target)
    return lifecycle_service.transition(task.task_id, state) if task.current_state != state else task


def _plan(task_id):
    return AgentTaskFailureRecoveryPlan(
        task_id=task_id,
        failure_event_id="evt-1",
        failure_category="execution",
        recommended_action=RECOVERY_ACTION_RETRY,
        reason="transient execution failure",
        priority=1,
        blocking_conditions=(),
    )


def _stack():
    lifecycle_service = LLMAgentTaskLifecycleService()
    preflight_store = LLMAgentTaskRecoveryPreflightStore()
    authorization_store = InMemoryAgentTaskRecoveryPreflightAuthorizationStore()
    authorization_service = LLMAgentTaskRecoveryPreflightAuthorizationService(store=authorization_store)
    snapshot_service = LLMAgentTaskRecoveryExecutionPreconditionSnapshotService(
        authorization_service=authorization_service,
        preflight_store=preflight_store,
        lifecycle_service=lifecycle_service,
    )
    return {
        "lifecycle_service": lifecycle_service,
        "preflight_store": preflight_store,
        "authorization_store": authorization_store,
        "authorization_service": authorization_service,
        "snapshot_service": snapshot_service,
    }


def _authorize(stack, task_id, plan=None, status=ACTIVE):
    preflight_id = stack["preflight_store"].save(
        AgentTaskRecoveryPreflightResult(
            task_id=task_id, plan=plan, guard_result=None, decision=ALLOW,
            blocking_reasons=(), warnings=(), checked_at=NOW,
        )
    ).preflight_id
    authorization = stack["authorization_store"].save(
        AgentTaskRecoveryPreflightAuthorization(
            task_id=task_id, preflight_id=preflight_id, approval_id="approval-1",
            status=status, revocation_reason=None, created_at=NOW, revoked_at=None,
        )
    )
    return authorization


def test_capture_binds_snapshot_to_exact_authorization_and_plan():
    s = _stack()
    task = _task(s["lifecycle_service"])
    plan = _plan(task.task_id)
    authorization = _authorize(s, task.task_id, plan=plan)

    snapshot = s["snapshot_service"].capture(task.task_id, authorization.authorization_id)

    assert snapshot.task_id == task.task_id
    assert snapshot.authorization_id == authorization.authorization_id
    assert snapshot.preflight_id == authorization.preflight_id
    assert snapshot.approval_id == authorization.approval_id
    assert snapshot.authorization_status == ACTIVE
    assert snapshot.recovery_plan == plan
    assert snapshot.task_state == task.current_state


def test_capture_rejects_unknown_authorization():
    s = _stack()
    task = _task(s["lifecycle_service"])

    with pytest.raises(InvalidAgentTaskRecoveryExecutionPreconditionSnapshotError):
        s["snapshot_service"].capture(task.task_id, "no-such-authorization")


def test_capture_rejects_revoked_authorization():
    s = _stack()
    task = _task(s["lifecycle_service"])
    authorization = _authorize(s, task.task_id, plan=_plan(task.task_id))
    s["authorization_service"].revoke(task.task_id, authorization.authorization_id, "no longer needed")

    with pytest.raises(InvalidAgentTaskRecoveryExecutionPreconditionSnapshotError):
        s["snapshot_service"].capture(task.task_id, authorization.authorization_id)


def test_get_isolates_by_task_id():
    s = _stack()
    task = _task(s["lifecycle_service"])
    other_task = _task(s["lifecycle_service"], objective="a different task")
    authorization = _authorize(s, task.task_id, plan=_plan(task.task_id))

    snapshot = s["snapshot_service"].capture(task.task_id, authorization.authorization_id)

    assert s["snapshot_service"].get(task.task_id, snapshot.snapshot_id) == snapshot
    assert s["snapshot_service"].get(other_task.task_id, snapshot.snapshot_id) is None


def test_compare_reports_unchanged_state():
    s = _stack()
    task = _task(s["lifecycle_service"])
    authorization = _authorize(s, task.task_id, plan=_plan(task.task_id))
    snapshot = s["snapshot_service"].capture(task.task_id, authorization.authorization_id)

    diff = s["snapshot_service"].compare(task.task_id, snapshot.snapshot_id)

    assert diff.changed is False
    assert diff.changes == ()
    assert diff.authorization_status_changed is False
    assert diff.task_state_changed is False


def test_compare_detects_task_state_change():
    s = _stack()
    task = _task(s["lifecycle_service"])
    authorization = _authorize(s, task.task_id, plan=_plan(task.task_id))
    snapshot = s["snapshot_service"].capture(task.task_id, authorization.authorization_id)

    s["lifecycle_service"].transition(task.task_id, PLANNED)

    diff = s["snapshot_service"].compare(task.task_id, snapshot.snapshot_id)

    assert diff.changed is True
    assert diff.task_state_changed is True
    assert diff.current_task_state == PLANNED
    changed_fields = {change.field for change in diff.changes}
    assert "task_state" in changed_fields


def test_compare_detects_authorization_revocation():
    s = _stack()
    task = _task(s["lifecycle_service"])
    authorization = _authorize(s, task.task_id, plan=_plan(task.task_id))
    snapshot = s["snapshot_service"].capture(task.task_id, authorization.authorization_id)

    s["authorization_service"].revoke(task.task_id, authorization.authorization_id, "revoked mid-flight")

    diff = s["snapshot_service"].compare(task.task_id, snapshot.snapshot_id)

    assert diff.changed is True
    assert diff.authorization_status_changed is True
    assert diff.current_authorization_status != ACTIVE


def test_compare_rejects_unknown_snapshot():
    s = _stack()
    task = _task(s["lifecycle_service"])

    with pytest.raises(InvalidAgentTaskRecoveryExecutionPreconditionSnapshotError):
        s["snapshot_service"].compare(task.task_id, "no-such-snapshot")


def test_snapshot_is_immutable_and_history_is_append_only():
    s = _stack()
    task = _task(s["lifecycle_service"])
    authorization = _authorize(s, task.task_id, plan=_plan(task.task_id))

    first = s["snapshot_service"].capture(task.task_id, authorization.authorization_id)
    with pytest.raises(dataclasses.FrozenInstanceError):
        first.task_state = "tampered"

    second = s["snapshot_service"].capture(task.task_id, authorization.authorization_id)

    assert first.snapshot_id != second.snapshot_id
    assert s["snapshot_service"].get(task.task_id, first.snapshot_id) == first
    assert s["snapshot_service"].get(task.task_id, second.snapshot_id) == second
