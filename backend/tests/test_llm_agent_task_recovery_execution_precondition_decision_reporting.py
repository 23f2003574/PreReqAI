from datetime import datetime, timedelta, timezone

import pytest

from backend.agent_task_recovery_execution_precondition_snapshots import (
    EXECUTION_DECISION_ALLOW,
    EXECUTION_DECISION_BLOCK,
    EXECUTION_DECISION_REVIEW,
    AgentTaskRecoveryExecutionPreconditionDecision,
    InvalidAgentTaskRecoveryExecutionPreconditionDecisionReportError,
    LLMAgentTaskRecoveryExecutionPreconditionDecisionHistoryService,
    LLMAgentTaskRecoveryExecutionPreconditionDecisionReportingService,
    LLMAgentTaskRecoveryExecutionPreconditionDecisionStore,
)

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
TASK_ID = "task-1"


def _decision(decision=EXECUTION_DECISION_ALLOW, created_at=NOW, blocking_conditions=(), warnings=()):
    return AgentTaskRecoveryExecutionPreconditionDecision(
        task_id=TASK_ID, snapshot_id="snap-1", authorization_id="auth-1", decision=decision,
        reason="test reason", blocking_conditions=blocking_conditions, warnings=warnings,
        validation_result=None, drift_classification=None, approval_reconciliation=None, created_at=created_at,
    )


def _stack():
    store = LLMAgentTaskRecoveryExecutionPreconditionDecisionStore()
    history_service = LLMAgentTaskRecoveryExecutionPreconditionDecisionHistoryService(store=store)
    service = LLMAgentTaskRecoveryExecutionPreconditionDecisionReportingService(history_service=history_service)
    return store, service


def test_empty_task_history_produces_valid_empty_report():
    _, service = _stack()

    report = service.report(TASK_ID)

    assert report.task_id == TASK_ID
    assert report.latest_decision is None
    assert report.latest_decision_at is None
    assert report.current_eligible is False
    assert report.decision_count == 0
    assert report.transition_count == 0
    assert report.latest_transition is None
    assert report.material_changes == ()
    assert report.blocking_conditions == ()
    assert report.warnings == ()
    assert report.decision_history == ()


def test_single_decision_report():
    store, service = _stack()
    only = store.save(_decision(decision=EXECUTION_DECISION_ALLOW))

    report = service.report(TASK_ID)

    assert report.latest_decision == only
    assert report.latest_decision_at == only.created_at
    assert report.current_eligible is True
    assert report.decision_count == 1
    assert report.transition_count == 0
    assert report.latest_transition is None


def test_multiple_decisions_latest_and_eligibility():
    store, service = _stack()
    store.save(_decision(decision=EXECUTION_DECISION_ALLOW, created_at=NOW))
    second = store.save(_decision(decision=EXECUTION_DECISION_BLOCK, created_at=NOW + timedelta(seconds=1)))

    report = service.report(TASK_ID)

    assert report.latest_decision == second
    assert report.current_eligible is False


def test_state_counts():
    store, service = _stack()
    store.save(_decision(decision=EXECUTION_DECISION_ALLOW, created_at=NOW))
    store.save(_decision(decision=EXECUTION_DECISION_REVIEW, created_at=NOW + timedelta(seconds=1)))
    store.save(_decision(decision=EXECUTION_DECISION_BLOCK, created_at=NOW + timedelta(seconds=2)))

    report = service.report(TASK_ID)

    assert report.counts_by_decision[EXECUTION_DECISION_ALLOW] == 1
    assert report.counts_by_decision[EXECUTION_DECISION_REVIEW] == 1
    assert report.counts_by_decision[EXECUTION_DECISION_BLOCK] == 1


def test_transition_metrics():
    store, service = _stack()
    store.save(_decision(decision=EXECUTION_DECISION_ALLOW, created_at=NOW))
    store.save(_decision(decision=EXECUTION_DECISION_REVIEW, created_at=NOW + timedelta(seconds=1)))
    store.save(_decision(decision=EXECUTION_DECISION_BLOCK, created_at=NOW + timedelta(seconds=2)))

    report = service.report(TASK_ID)

    assert report.transition_count == 2
    assert report.eligibility_change_count == 1
    assert report.review_or_block_transition_count == 2


def test_latest_transition_details():
    store, service = _stack()
    store.save(_decision(decision=EXECUTION_DECISION_ALLOW, created_at=NOW))
    store.save(_decision(decision=EXECUTION_DECISION_REVIEW, created_at=NOW + timedelta(seconds=1)))

    report = service.report(TASK_ID)

    assert report.latest_transition.transition_type == "allow_to_review"
    assert report.latest_transition.requires_attention is True
    assert bool(report.material_changes)


def test_blockers_and_warnings_propagate_from_latest_decision():
    store, service = _stack()
    store.save(_decision(decision=EXECUTION_DECISION_ALLOW, created_at=NOW))
    store.save(
        _decision(
            decision=EXECUTION_DECISION_BLOCK, blocking_conditions=("dependency unresolved",),
            warnings=("stale plan",), created_at=NOW + timedelta(seconds=1),
        )
    )

    report = service.report(TASK_ID)

    assert report.blocking_conditions == ("dependency unresolved",)
    assert report.warnings == ("stale plan",)


def test_history_limiting():
    store, service = _stack()
    for i in range(5):
        store.save(_decision(decision=EXECUTION_DECISION_ALLOW, created_at=NOW + timedelta(seconds=i)))

    report = service.report(TASK_ID, limit=2)

    assert len(report.decision_history) == 2
    assert report.decision_count == 5


def test_report_rejects_blank_task_id():
    _, service = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryExecutionPreconditionDecisionReportError):
        service.report("")


def test_report_rejects_invalid_limit():
    _, service = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryExecutionPreconditionDecisionReportError):
        service.report(TASK_ID, limit=0)


def test_report_structure_is_deterministic():
    store, service = _stack()
    store.save(_decision(decision=EXECUTION_DECISION_ALLOW, created_at=NOW))
    store.save(_decision(decision=EXECUTION_DECISION_REVIEW, created_at=NOW + timedelta(seconds=1)))

    first = service.report(TASK_ID)
    second = service.report(TASK_ID)

    assert first.decision_count == second.decision_count
    assert first.transition_count == second.transition_count
    assert first.latest_transition.transition_type == second.latest_transition.transition_type
    assert [d.decision_id for d in first.decision_history] == [d.decision_id for d in second.decision_history]
