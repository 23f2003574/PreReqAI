import pytest

from backend.agent_task_event_analytics import (
    InvalidAgentTaskRecoveryHistoryError,
    LLMAgentTaskRecoveryHistoryService,
    LLMAgentTaskRecoveryOutcomeService,
    RECOVERY_ACTION_MARK_UNRECOVERABLE,
    RECOVERY_ACTION_REPAIR_TASK,
    RECOVERY_ACTION_RETRY,
    RECOVERY_OUTCOME_FAILED,
    RECOVERY_OUTCOME_PARTIAL,
    RECOVERY_OUTCOME_SUCCESS,
    AgentTaskFailureRecoveryResult,
)
from backend.agent_task_events import InMemoryAgentTaskEventStore, LLMAgentTaskEventQueryService, LLMAgentTaskEventService


def _services():
    store = InMemoryAgentTaskEventStore()
    event_service = LLMAgentTaskEventService(store=store)
    query_service = LLMAgentTaskEventQueryService(store=store)
    outcome_service = LLMAgentTaskRecoveryOutcomeService(event_service=event_service, query_service=query_service)
    history_service = LLMAgentTaskRecoveryHistoryService(outcome_service=outcome_service)
    return outcome_service, history_service


def _result(task_id="task-1", **overrides):
    fields = dict(
        task_id=task_id,
        planned_action=RECOVERY_ACTION_RETRY,
        executed_action=RECOVERY_ACTION_RETRY,
        success=True,
        failure_reason=None,
        affected_reference="retry scheduled: attempt 1",
        source_failure_event_id="failure-event-1",
        partial=False,
    )
    fields.update(overrides)
    return AgentTaskFailureRecoveryResult(**fields)


# --- empty history -----------------------------------------------------------------------------


def test_empty_history_get_returns_empty_list():
    _, history_service = _services()

    assert history_service.get("task-1") == []


def test_empty_history_latest_returns_none():
    _, history_service = _services()

    assert history_service.latest("task-1") is None


def test_empty_history_summary_is_all_zeroed():
    _, history_service = _services()

    summary = history_service.summarize("task-1")

    assert summary.total_attempts == 0
    assert summary.successful_attempts == 0
    assert summary.failed_attempts == 0
    assert summary.partial_attempts == 0
    assert summary.latest_status is None
    assert summary.latest_action is None


def test_get_rejects_blank_task_id():
    _, history_service = _services()

    with pytest.raises(InvalidAgentTaskRecoveryHistoryError):
        history_service.get("")


# --- multiple recovery attempts --------------------------------------------------------------------


def test_multiple_recovery_attempts_are_all_returned():
    outcome_service, history_service = _services()
    outcome_service.record("task-1", _result(source_failure_event_id="failure-1"))
    outcome_service.record("task-1", _result(source_failure_event_id="failure-2"))
    outcome_service.record("task-1", _result(source_failure_event_id="failure-3"))

    history = history_service.get("task-1")

    assert len(history) == 3


# --- latest outcome ----------------------------------------------------------------------------------


def test_latest_returns_the_most_recent_outcome():
    outcome_service, history_service = _services()
    outcome_service.record("task-1", _result(source_failure_event_id="failure-1"))
    latest = outcome_service.record("task-1", _result(source_failure_event_id="failure-2"))

    assert history_service.latest("task-1") == latest


def test_latest_preserves_the_complete_outcome_object():
    outcome_service, history_service = _services()
    recorded = outcome_service.record("task-1", _result())

    latest = history_service.latest("task-1")

    assert latest.recovery_id == recorded.recovery_id
    assert latest.source_failure_event_id == recorded.source_failure_event_id
    assert latest.started_at == recorded.started_at


# --- success/failure counts --------------------------------------------------------------------------


def test_summary_counts_success_failure_and_partial_separately():
    outcome_service, history_service = _services()
    outcome_service.record(
        "task-1", _result(source_failure_event_id="f-1", success=True, executed_action=RECOVERY_ACTION_RETRY)
    )
    outcome_service.record(
        "task-1",
        _result(
            source_failure_event_id="f-2",
            success=False,
            executed_action=RECOVERY_ACTION_MARK_UNRECOVERABLE,
            failure_reason="no service supplied",
        ),
    )
    outcome_service.record(
        "task-1",
        _result(
            source_failure_event_id="f-3",
            success=True,
            partial=True,
            planned_action=RECOVERY_ACTION_REPAIR_TASK,
            executed_action=RECOVERY_ACTION_REPAIR_TASK,
            affected_reference="repair applied: final_status=PARTIAL",
        ),
    )

    summary = history_service.summarize("task-1")

    assert summary.total_attempts == 3
    assert summary.successful_attempts == 1
    assert summary.failed_attempts == 1
    assert summary.partial_attempts == 1
    assert summary.latest_status == RECOVERY_OUTCOME_PARTIAL
    assert summary.latest_action == RECOVERY_ACTION_REPAIR_TASK


def test_latest_action_falls_back_to_planned_action_when_nothing_executed():
    outcome_service, history_service = _services()
    outcome_service.record(
        "task-1",
        _result(executed_action=None, success=False, failure_reason="unsupported"),
    )

    summary = history_service.summarize("task-1")

    assert summary.latest_action == RECOVERY_ACTION_RETRY  # falls back to planned_action


# --- deterministic ordering -------------------------------------------------------------------------------


def test_get_orders_outcomes_oldest_to_newest_deterministically():
    outcome_service, history_service = _services()
    first = outcome_service.record("task-1", _result(source_failure_event_id="f-1"))
    second = outcome_service.record("task-1", _result(source_failure_event_id="f-2"))
    third = outcome_service.record("task-1", _result(source_failure_event_id="f-3"))

    history = history_service.get("task-1")

    assert [o.recovery_id for o in history] == [first.recovery_id, second.recovery_id, third.recovery_id]


def test_repeated_get_is_deterministic():
    outcome_service, history_service = _services()
    outcome_service.record("task-1", _result(source_failure_event_id="f-1"))
    outcome_service.record("task-1", _result(source_failure_event_id="f-2"))

    assert history_service.get("task-1") == history_service.get("task-1")


def test_repeated_summarize_is_deterministic():
    outcome_service, history_service = _services()
    outcome_service.record("task-1", _result())

    assert history_service.summarize("task-1") == history_service.summarize("task-1")


# --- limit handling -------------------------------------------------------------------------------------------


def test_get_limit_caps_to_most_recent_entries_oldest_to_newest():
    outcome_service, history_service = _services()
    outcome_service.record("task-1", _result(source_failure_event_id="f-1"))
    second = outcome_service.record("task-1", _result(source_failure_event_id="f-2"))
    third = outcome_service.record("task-1", _result(source_failure_event_id="f-3"))

    limited = history_service.get("task-1", limit=2)

    assert [o.recovery_id for o in limited] == [second.recovery_id, third.recovery_id]


def test_get_limit_zero_returns_empty_list():
    outcome_service, history_service = _services()
    outcome_service.record("task-1", _result())

    assert history_service.get("task-1", limit=0) == []


def test_get_rejects_negative_limit():
    _, history_service = _services()

    with pytest.raises(InvalidAgentTaskRecoveryHistoryError):
        history_service.get("task-1", limit=-1)


# --- multiple tasks remain isolated -----------------------------------------------------------------------------


def test_multiple_tasks_remain_isolated():
    outcome_service, history_service = _services()
    outcome_service.record("task-1", _result(task_id="task-1"))
    outcome_service.record("task-2", _result(task_id="task-2"))
    outcome_service.record("task-2", _result(task_id="task-2", source_failure_event_id="f-2"))

    assert len(history_service.get("task-1")) == 1
    assert len(history_service.get("task-2")) == 2
    assert history_service.summarize("task-1").total_attempts == 1
    assert history_service.summarize("task-2").total_attempts == 2
