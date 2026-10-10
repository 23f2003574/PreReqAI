from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from backend.agent_task_recovery_scheduling import (
    BATCH_CLEANED,
    BATCH_FAILED,
    PROTECTED_LATEST,
    PROTECTED_UNRESOLVED_FAILURE,
    AgentTaskRecoveryScheduleCleanupBatchEntry,
    AgentTaskRecoveryScheduleCleanupBatchResult,
    InMemoryAgentTaskRecoveryScheduleCleanupResultStore,
    InvalidAgentTaskRecoveryScheduleCleanupResultRetentionError,
    JsonAgentTaskRecoveryScheduleCleanupResultStore,
    LLMAgentTaskRecoveryPreflightScheduleCleanupResultRetentionService,
    LLMAgentTaskRecoveryPreflightScheduleCleanupResultService,
)

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
BEFORE = T0 + timedelta(days=10)


def _batch(day, *entries, task_id="task-1"):
    """entries: (schedule_id, outcome) pairs."""
    built = tuple(
        AgentTaskRecoveryScheduleCleanupBatchEntry(
            sid, outcome, "expired" if outcome == BATCH_CLEANED else None, "boom" if outcome == BATCH_FAILED else None
        )
        for sid, outcome in entries
    )
    count = lambda outcome: sum(1 for e in built if e.outcome == outcome)
    return AgentTaskRecoveryScheduleCleanupBatchResult(
        task_id=task_id, executed_at=T0 + timedelta(days=day), entries=built,
        cleaned_count=count(BATCH_CLEANED), skipped_count=0, failed_count=count(BATCH_FAILED),
    )


@pytest.fixture(params=["memory", "json"])
def results(request, tmp_path):
    if request.param == "memory":
        store = InMemoryAgentTaskRecoveryScheduleCleanupResultStore()
    else:
        store = JsonAgentTaskRecoveryScheduleCleanupResultStore(tmp_path / "results.json")
    return LLMAgentTaskRecoveryPreflightScheduleCleanupResultService(store=store)


@pytest.fixture
def retention(results):
    return LLMAgentTaskRecoveryPreflightScheduleCleanupResultRetentionService(result_service=results)


def _ids(results):
    return [r.result_id for r in results.history("task-1")]


def test_old_resolved_results_are_eligible_and_removed(results, retention):
    old = [results.record("task-1", _batch(day, ("s1", BATCH_CLEANED))) for day in (1, 2)]
    latest = results.record("task-1", _batch(20, ("s2", BATCH_CLEANED)))

    plan = retention.plan("task-1", before=BEFORE)
    outcome = retention.apply("task-1", plan)

    assert plan.eligible == (old[0].result_id, old[1].result_id)
    assert plan.protected == ()
    assert outcome.removed == plan.eligible
    assert _ids(results) == [latest.result_id]


def test_latest_result_is_never_removed_even_when_old(results, retention):
    only = results.record("task-1", _batch(1, ("s1", BATCH_CLEANED)))

    plan = retention.plan("task-1", before=BEFORE)

    assert plan.eligible == ()
    assert plan.protected == ((only.result_id, PROTECTED_LATEST),)
    assert retention.apply("task-1", plan).removed == ()
    assert _ids(results) == [only.result_id]


def test_unresolved_failure_is_protected_until_a_later_result_resolves_it(results, retention):
    failed = results.record("task-1", _batch(1, ("s1", BATCH_FAILED)))
    results.record("task-1", _batch(2, ("s2", BATCH_CLEANED)))
    results.record("task-1", _batch(20, ("s3", BATCH_CLEANED)))

    assert retention.plan("task-1", before=BEFORE).protected == ((failed.result_id, PROTECTED_UNRESOLVED_FAILURE),)

    results.record("task-1", _batch(3, ("s1", BATCH_CLEANED)))
    plan = retention.plan("task-1", before=BEFORE)

    assert failed.result_id in plan.eligible
    assert plan.protected == ()


def test_results_after_the_cutoff_are_not_candidates_and_boundary_is_inclusive(results, retention):
    at_cutoff = results.record("task-1", _batch(10, ("s1", BATCH_CLEANED)))
    after_cutoff = results.record("task-1", replace(_batch(10, ("s3", BATCH_CLEANED)), executed_at=BEFORE + timedelta(seconds=1)))
    latest = results.record("task-1", _batch(30, ("s4", BATCH_CLEANED)))

    plan = retention.plan("task-1", before=BEFORE)

    assert at_cutoff.result_id in plan.eligible
    assert after_cutoff.result_id not in plan.eligible + tuple(i for i, _ in plan.protected)
    assert latest.result_id not in plan.eligible


def test_default_cutoff_uses_the_events_retention_window(results):
    from backend.agent_task_events.retention import DEFAULT_RETENTION_WINDOW

    plan = LLMAgentTaskRecoveryPreflightScheduleCleanupResultRetentionService(result_service=results).plan("task-1")

    assert datetime.now(timezone.utc) - plan.before - DEFAULT_RETENTION_WINDOW < timedelta(seconds=5)


def test_plan_is_read_only_and_apply_is_idempotent(results, retention):
    results.record("task-1", _batch(1, ("s1", BATCH_CLEANED)))
    results.record("task-1", _batch(2, ("s2", BATCH_CLEANED)))
    results.record("task-1", _batch(20, ("s3", BATCH_CLEANED)))
    before = results.history("task-1")

    plan = retention.plan("task-1", before=BEFORE)
    assert retention.plan("task-1", before=BEFORE) == plan
    assert results.history("task-1") == before

    first = retention.apply("task-1", plan)
    second = retention.apply("task-1", plan)

    assert len(first.removed) == 2
    assert (second.removed, second.already_removed) == ((), plan.eligible)
    assert len(results.history("task-1")) == 1
    assert retention.apply("task-1").removed == ()


def test_forged_plan_cannot_remove_protected_results(results, retention):
    failed = results.record("task-1", _batch(1, ("s1", BATCH_FAILED)))
    latest = results.record("task-1", _batch(2, ("s2", BATCH_CLEANED)))
    plan = retention.plan("task-1", before=BEFORE)
    forged = replace(plan, eligible=(failed.result_id, latest.result_id))

    outcome = retention.apply("task-1", forged)

    assert outcome.removed == ()
    assert outcome.newly_protected == (
        (failed.result_id, PROTECTED_UNRESOLVED_FAILURE), (latest.result_id, PROTECTED_LATEST),
    )
    assert _ids(results) == [failed.result_id, latest.result_id]


def test_retention_is_scoped_to_one_task(results, retention):
    results.record("task-2", _batch(1, ("s1", BATCH_CLEANED), task_id="task-2"))
    results.record("task-2", _batch(2, ("s2", BATCH_CLEANED), task_id="task-2"))

    assert retention.plan("task-1", before=BEFORE).eligible == ()
    assert retention.apply("task-1").removed == ()
    assert len(results.history("task-2")) == 2


def test_empty_history_plans_and_applies_nothing(retention):
    plan = retention.plan("task-1", before=BEFORE)

    assert (plan.eligible, plan.protected) == ((), ())
    assert retention.apply("task-1", plan).removed == ()


def test_invalid_arguments_are_rejected(retention):
    plan = retention.plan("task-1", before=BEFORE)
    for call in (
        lambda: retention.plan(""),
        lambda: retention.plan("task-1", before="yesterday"),
        lambda: retention.apply(None),
        lambda: retention.apply("task-1", ["r1"]),
        lambda: retention.apply("task-2", plan),
    ):
        with pytest.raises(InvalidAgentTaskRecoveryScheduleCleanupResultRetentionError):
            call()
