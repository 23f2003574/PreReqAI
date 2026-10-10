from datetime import datetime, timedelta, timezone

import pytest

from backend.agent_task_recovery_execution_precondition_snapshots import (
    FRESHNESS_FRESH,
    FRESHNESS_STALE,
    FRESHNESS_UNKNOWN,
    REVALIDATION_FAILED,
    REVALIDATION_REPLACED,
    AgentTaskRecoveryExecutionDecisionStalenessResult,
    AgentTaskRecoveryExecutionDecisionFreshnessRevalidationResult,
    InvalidAgentTaskRecoveryExecutionDecisionFreshnessAuditError,
    LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService,
)

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
TASK_ID = "task-1"
DECISION_ID = "decision-1"


def _staleness(status=FRESHNESS_FRESH, reason="ok", decision_v="snap-1", current_v="snap-1"):
    return AgentTaskRecoveryExecutionDecisionStalenessResult(
        task_id=TASK_ID, decision_id=DECISION_ID, status=status, reason=reason,
        decision_timestamp=NOW, current_state_version=current_v, decision_state_version=decision_v,
        checked_at=NOW,
    )


def _revalidation(action=REVALIDATION_REPLACED, new_decision_id="decision-2"):
    return AgentTaskRecoveryExecutionDecisionFreshnessRevalidationResult(
        task_id=TASK_ID, old_decision_id=DECISION_ID, new_decision_id=new_decision_id, action=action,
        staleness=_staleness(status=FRESHNESS_STALE), old_decision=None, new_decision=None, reason=None,
        revalidated_at=NOW,
    )


def test_record_fresh_acceptance():
    service = LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService()

    record = service.record(TASK_ID, DECISION_ID, _staleness(status=FRESHNESS_FRESH))

    assert record.freshness_status == FRESHNESS_FRESH
    assert record.revalidated is False
    assert record.replacement_decision_id is None


def test_record_stale_rejection():
    service = LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService()

    record = service.record(TASK_ID, DECISION_ID, _staleness(status=FRESHNESS_STALE, reason="drifted"))

    assert record.freshness_status == FRESHNESS_STALE
    assert record.freshness_reason == "drifted"


def test_record_indeterminate_rejection():
    service = LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService()

    record = service.record(TASK_ID, DECISION_ID, _staleness(status=FRESHNESS_UNKNOWN, reason="ambiguous"))

    assert record.freshness_status == FRESHNESS_UNKNOWN


def test_record_successful_revalidation_links_replacement():
    service = LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService()

    record = service.record(
        TASK_ID, DECISION_ID, _staleness(status=FRESHNESS_STALE),
        revalidation_result=_revalidation(action=REVALIDATION_REPLACED, new_decision_id="decision-2"),
    )

    assert record.revalidated is True
    assert record.revalidation_action == REVALIDATION_REPLACED
    assert record.replacement_decision_id == "decision-2"


def test_record_failed_revalidation_has_no_replacement():
    service = LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService()

    record = service.record(
        TASK_ID, DECISION_ID, _staleness(status=FRESHNESS_STALE),
        revalidation_result=_revalidation(action=REVALIDATION_FAILED, new_decision_id=None),
    )

    assert record.revalidated is True
    assert record.revalidation_action == REVALIDATION_FAILED
    assert record.replacement_decision_id is None


def test_duplicate_recording_is_idempotent():
    service = LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService()

    first = service.record(TASK_ID, DECISION_ID, _staleness(status=FRESHNESS_FRESH))
    second = service.record(TASK_ID, DECISION_ID, _staleness(status=FRESHNESS_FRESH))

    assert first.audit_id == second.audit_id
    assert len(service.list(TASK_ID)) == 1


def test_different_evaluation_is_appended_not_deduped():
    service = LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService()

    first = service.record(TASK_ID, DECISION_ID, _staleness(status=FRESHNESS_FRESH))
    second = service.record(TASK_ID, DECISION_ID, _staleness(status=FRESHNESS_STALE, reason="drifted"))

    assert first.audit_id != second.audit_id
    assert len(service.list(TASK_ID)) == 2


def test_history_is_chronological_and_preserved():
    service = LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService()

    r1 = service.record(TASK_ID, DECISION_ID, _staleness(status=FRESHNESS_FRESH))
    r2 = service.record(TASK_ID, DECISION_ID, _staleness(status=FRESHNESS_STALE, reason="drifted"))

    history = service.list(TASK_ID)
    assert [r.audit_id for r in history] == [r1.audit_id, r2.audit_id]
    assert service.get(r1.audit_id) == r1


def test_mismatched_freshness_result_raises():
    service = LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService()

    with pytest.raises(InvalidAgentTaskRecoveryExecutionDecisionFreshnessAuditError):
        service.record("other-task", DECISION_ID, _staleness())


def test_record_rejects_blank_arguments():
    service = LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService()
    with pytest.raises(InvalidAgentTaskRecoveryExecutionDecisionFreshnessAuditError):
        service.record("", DECISION_ID, _staleness())
    with pytest.raises(InvalidAgentTaskRecoveryExecutionDecisionFreshnessAuditError):
        service.record(TASK_ID, "", _staleness())


def test_missing_audit_returns_none():
    service = LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService()
    assert service.get("never-existed") is None
