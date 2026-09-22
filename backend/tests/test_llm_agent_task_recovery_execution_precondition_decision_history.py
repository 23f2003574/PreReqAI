from datetime import datetime, timedelta, timezone

import pytest

from backend.agent_task_recovery_execution_precondition_snapshots import (
    EXECUTION_DECISION_ALLOW,
    EXECUTION_DECISION_BLOCK,
    EXECUTION_DECISION_REVIEW,
    AgentTaskRecoveryExecutionPreconditionDecision,
    InvalidAgentTaskRecoveryExecutionPreconditionDecisionHistoryError,
    LLMAgentTaskRecoveryExecutionPreconditionDecisionHistoryService,
    LLMAgentTaskRecoveryExecutionPreconditionDecisionStore,
    LLMAgentTaskRecoveryExecutionPreconditionDecisionTransitionService,
)

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
TASK_ID = "task-1"


def _decision(decision=EXECUTION_DECISION_ALLOW, created_at=NOW):
    return AgentTaskRecoveryExecutionPreconditionDecision(
        task_id=TASK_ID, snapshot_id="snap-1", authorization_id="auth-1", decision=decision,
        reason="test reason", blocking_conditions=(), warnings=(), validation_result=None,
        drift_classification=None, approval_reconciliation=None, created_at=created_at,
    )


def _stack():
    store = LLMAgentTaskRecoveryExecutionPreconditionDecisionStore()
    transition_service = LLMAgentTaskRecoveryExecutionPreconditionDecisionTransitionService(store=store)
    service = LLMAgentTaskRecoveryExecutionPreconditionDecisionHistoryService(
        store=store, transition_service=transition_service
    )
    return store, service


def test_empty_history_is_valid():
    _, service = _stack()

    history = service.get_history(TASK_ID)

    assert history.decisions == ()
    assert history.first_decision is None
    assert history.latest_decision is None
    assert history.decision_count == 0
    assert history.transitions == ()
    assert history.eligibility_change_count == 0
    assert history.review_or_block_transition_count == 0
    assert history.current_eligible is False
    assert history.first_decision_at is None
    assert history.last_decision_at is None


def test_single_decision_history():
    store, service = _stack()
    only = store.save(_decision(decision=EXECUTION_DECISION_ALLOW))

    history = service.get_history(TASK_ID)

    assert history.decisions == (only,)
    assert history.first_decision == only
    assert history.latest_decision == only
    assert history.decision_count == 1
    assert history.transitions == ()
    assert history.current_eligible is True


def test_multiple_decisions_chronological_ordering():
    store, service = _stack()
    d1 = store.save(_decision(decision=EXECUTION_DECISION_ALLOW, created_at=NOW))
    d3 = store.save(_decision(decision=EXECUTION_DECISION_BLOCK, created_at=NOW + timedelta(seconds=2)))
    d2 = store.save(_decision(decision=EXECUTION_DECISION_REVIEW, created_at=NOW + timedelta(seconds=1)))

    history = service.get_history(TASK_ID)

    assert [d.decision_id for d in history.decisions] == [d1.decision_id, d2.decision_id, d3.decision_id]
    assert history.first_decision == d1
    assert history.latest_decision == d3
    assert history.current_eligible is False


def test_decision_state_counts():
    store, service = _stack()
    store.save(_decision(decision=EXECUTION_DECISION_ALLOW, created_at=NOW))
    store.save(_decision(decision=EXECUTION_DECISION_ALLOW, created_at=NOW + timedelta(seconds=1)))
    store.save(_decision(decision=EXECUTION_DECISION_REVIEW, created_at=NOW + timedelta(seconds=2)))
    store.save(_decision(decision=EXECUTION_DECISION_BLOCK, created_at=NOW + timedelta(seconds=3)))

    history = service.get_history(TASK_ID)

    assert history.counts_by_decision[EXECUTION_DECISION_ALLOW] == 2
    assert history.counts_by_decision[EXECUTION_DECISION_REVIEW] == 1
    assert history.counts_by_decision[EXECUTION_DECISION_BLOCK] == 1
    assert history.decision_count == 4


def test_transition_generation_and_eligibility_counting():
    store, service = _stack()
    store.save(_decision(decision=EXECUTION_DECISION_ALLOW, created_at=NOW))
    store.save(_decision(decision=EXECUTION_DECISION_REVIEW, created_at=NOW + timedelta(seconds=1)))
    store.save(_decision(decision=EXECUTION_DECISION_BLOCK, created_at=NOW + timedelta(seconds=2)))
    store.save(_decision(decision=EXECUTION_DECISION_ALLOW, created_at=NOW + timedelta(seconds=3)))

    history = service.get_history(TASK_ID)

    assert len(history.transitions) == 3
    assert [t.transition_type for t in history.transitions] == [
        "allow_to_review", "review_to_block", "block_to_allow",
    ]
    # allow->review (changed) , review->block (unchanged eligibility, both non-allow),
    # block->allow (changed)
    assert history.eligibility_change_count == 2


def test_review_or_block_transition_counting():
    store, service = _stack()
    store.save(_decision(decision=EXECUTION_DECISION_ALLOW, created_at=NOW))
    store.save(_decision(decision=EXECUTION_DECISION_REVIEW, created_at=NOW + timedelta(seconds=1)))
    store.save(_decision(decision=EXECUTION_DECISION_ALLOW, created_at=NOW + timedelta(seconds=2)))
    store.save(_decision(decision=EXECUTION_DECISION_BLOCK, created_at=NOW + timedelta(seconds=3)))

    history = service.get_history(TASK_ID)

    # transitions landing on review or block: allow->review, allow->block == 2
    assert history.review_or_block_transition_count == 2


def test_limit_returns_most_recent_records_but_full_aggregates():
    store, service = _stack()
    for i in range(5):
        store.save(_decision(decision=EXECUTION_DECISION_ALLOW, created_at=NOW + timedelta(seconds=i)))

    history = service.get_history(TASK_ID, limit=2)

    assert len(history.decisions) == 2
    assert history.decision_count == 5
    assert len(history.transitions) == 4
    assert history.decisions[0].created_at < history.decisions[1].created_at


def test_limit_rejects_non_positive_values():
    _, service = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryExecutionPreconditionDecisionHistoryError):
        service.get_history(TASK_ID, limit=0)
    with pytest.raises(InvalidAgentTaskRecoveryExecutionPreconditionDecisionHistoryError):
        service.get_history(TASK_ID, limit=-1)


def test_get_history_rejects_blank_task_id():
    _, service = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryExecutionPreconditionDecisionHistoryError):
        service.get_history("")


def test_summarize_matches_get_history_aggregates():
    store, service = _stack()
    store.save(_decision(decision=EXECUTION_DECISION_ALLOW, created_at=NOW))
    store.save(_decision(decision=EXECUTION_DECISION_BLOCK, created_at=NOW + timedelta(seconds=1)))

    history = service.get_history(TASK_ID)
    summary = service.summarize(TASK_ID)

    assert summary.decision_count == history.decision_count
    assert summary.counts_by_decision == history.counts_by_decision
    assert summary.eligibility_change_count == history.eligibility_change_count
    assert summary.review_or_block_transition_count == history.review_or_block_transition_count
    assert summary.current_eligible == history.current_eligible
    assert summary.latest_decision == history.latest_decision
    assert summary.first_decision_at == history.first_decision_at
    assert summary.last_decision_at == history.last_decision_at


def test_summarize_of_empty_history():
    _, service = _stack()
    summary = service.summarize(TASK_ID)

    assert summary.decision_count == 0
    assert summary.current_eligible is False
    assert summary.latest_decision is None
