import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from backend.agent_policy_engine import ALLOW, DENY
from backend.agent_task_event_analytics import (
    RECOVERY_ACTION_MARK_UNRECOVERABLE,
    RECOVERY_ACTION_RETRY,
    RECOVERY_PRIORITY_HIGH,
    AgentTaskFailureRecoveryPlan,
)
from backend.agent_task_recovery_guardrails import (
    AgentTaskRecoveryPreflightResult,
    InvalidAgentTaskRecoveryPreflightPersistenceError,
    JsonAgentTaskRecoveryPreflightStore,
    LLMAgentTaskRecoveryPreflightStore,
)


def _plan(task_id="task-1", action=RECOVERY_ACTION_RETRY, failure_event_id="f1"):
    return AgentTaskFailureRecoveryPlan(
        task_id=task_id, failure_event_id=failure_event_id, failure_category="execution",
        recommended_action=action, reason="test plan", priority=RECOVERY_PRIORITY_HIGH, blocking_conditions=(),
    )


def _preflight_result(task_id="task-1", plan=None, decision=ALLOW, blocking_reasons=(), warnings=(), checked_at=None):
    return AgentTaskRecoveryPreflightResult(
        task_id=task_id,
        plan=plan if plan is not None else _plan(task_id=task_id),
        guard_result=None,
        decision=decision,
        blocking_reasons=blocking_reasons,
        warnings=warnings,
        checked_at=checked_at if checked_at is not None else datetime.now(timezone.utc),
    )


# --- save/get --------------------------------------------------------------


def test_save_and_get():
    store = LLMAgentTaskRecoveryPreflightStore()
    preflight = _preflight_result()

    saved = store.save(preflight)
    fetched = store.get("task-1")

    assert fetched == saved
    assert fetched.task_id == "task-1"
    assert fetched.decision == ALLOW
    assert fetched.preflight_id


def test_get_rejects_blank_task_id():
    store = LLMAgentTaskRecoveryPreflightStore()
    with pytest.raises(InvalidAgentTaskRecoveryPreflightPersistenceError):
        store.get("")


def test_save_rejects_wrong_type():
    store = LLMAgentTaskRecoveryPreflightStore()
    with pytest.raises(InvalidAgentTaskRecoveryPreflightPersistenceError):
        store.save("not-a-preflight-result")


# --- multiple preflights preserve history --------------------------------------------------------------


def test_multiple_preflights_preserve_history():
    store = LLMAgentTaskRecoveryPreflightStore()
    first = store.save(_preflight_result(decision=ALLOW, checked_at=datetime(2026, 1, 1, tzinfo=timezone.utc)))
    second = store.save(
        _preflight_result(
            decision=DENY,
            blocking_reasons=("something broke",),
            checked_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        )
    )

    history = store.history("task-1")

    assert len(history) == 2
    assert history[0] == first
    assert history[1] == second
    assert store.get("task-1") == second


def test_missing_task_history_is_empty():
    store = LLMAgentTaskRecoveryPreflightStore()

    assert store.history("nonexistent-task") == []


# --- deterministic ordering --------------------------------------------------------------


def test_history_ordering_is_deterministic_and_by_checked_at():
    store = LLMAgentTaskRecoveryPreflightStore()
    later = store.save(_preflight_result(decision=ALLOW, checked_at=datetime(2026, 1, 5, tzinfo=timezone.utc)))
    earlier = store.save(
        _preflight_result(
            decision=DENY, blocking_reasons=("x",), checked_at=datetime(2026, 1, 1, tzinfo=timezone.utc)
        )
    )

    history_1 = store.history("task-1")
    history_2 = store.history("task-1")

    assert history_1 == history_2
    assert history_1 == [earlier, later]


def test_history_limit_returns_most_recent_still_oldest_to_newest():
    store = LLMAgentTaskRecoveryPreflightStore()
    for day in range(1, 4):
        store.save(
            _preflight_result(
                decision=DENY, blocking_reasons=(f"reason-{day}",), checked_at=datetime(2026, 1, day, tzinfo=timezone.utc)
            )
        )

    limited = store.history("task-1", limit=2)

    assert len(limited) == 2
    assert limited[0].blocking_reasons == ("reason-2",)
    assert limited[1].blocking_reasons == ("reason-3",)


def test_history_limit_rejects_negative():
    store = LLMAgentTaskRecoveryPreflightStore()
    store.save(_preflight_result())
    with pytest.raises(InvalidAgentTaskRecoveryPreflightPersistenceError):
        store.history("task-1", limit=-1)


# --- duplicate save/idempotency --------------------------------------------------------------


def test_duplicate_save_is_idempotent():
    store = LLMAgentTaskRecoveryPreflightStore()
    fixed_now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    preflight = _preflight_result(checked_at=fixed_now)

    first = store.save(preflight)
    second = store.save(_preflight_result(checked_at=fixed_now + timedelta(minutes=5)))  # same content, later checked_at

    assert first.preflight_id == second.preflight_id
    assert len(store.history("task-1")) == 1


def test_genuinely_distinct_preflights_both_persist():
    store = LLMAgentTaskRecoveryPreflightStore()
    store.save(_preflight_result(decision=ALLOW))
    store.save(_preflight_result(decision=DENY, blocking_reasons=("blocked",)))

    assert len(store.history("task-1")) == 2


# --- missing task --------------------------------------------------------------


def test_get_missing_task_returns_none():
    store = LLMAgentTaskRecoveryPreflightStore()

    assert store.get("never-saved-task") is None


# --- blocked and allowed results --------------------------------------------------------------


def test_blocked_and_allowed_results_both_stored_faithfully():
    store = LLMAgentTaskRecoveryPreflightStore()
    allowed = store.save(_preflight_result(task_id="task-allowed", decision=ALLOW))
    blocked = store.save(
        _preflight_result(
            task_id="task-blocked",
            decision=DENY,
            blocking_reasons=("policy denies task execution",),
            plan=_plan(task_id="task-blocked", action=RECOVERY_ACTION_MARK_UNRECOVERABLE),
        )
    )

    assert store.get("task-allowed").decision == ALLOW
    assert store.get("task-allowed").blocking_reasons == ()
    assert store.get("task-blocked").decision == DENY
    assert store.get("task-blocked").blocking_reasons == ("policy denies task execution",)
    assert store.get("task-blocked").plan.recommended_action == RECOVERY_ACTION_MARK_UNRECOVERABLE


def test_planner_failure_preflight_with_no_plan_is_stored():
    store = LLMAgentTaskRecoveryPreflightStore()
    preflight = AgentTaskRecoveryPreflightResult(
        task_id="task-1", plan=None, guard_result=None, decision=DENY,
        blocking_reasons=("recovery planning failed: boom",), warnings=(), checked_at=datetime.now(timezone.utc),
    )

    saved = store.save(preflight)
    fetched = store.get("task-1")

    assert saved.plan is None
    assert fetched.plan is None
    assert fetched.blocking_reasons == ("recovery planning failed: boom",)


# --- stored data matches original preflight --------------------------------------------------------------


def test_stored_data_matches_original_preflight():
    plan = _plan()
    checked_at = datetime(2026, 3, 1, tzinfo=timezone.utc)
    preflight = _preflight_result(
        plan=plan, decision=DENY, blocking_reasons=("a violation",), warnings=("a warning",), checked_at=checked_at
    )
    store = LLMAgentTaskRecoveryPreflightStore()

    saved = store.save(preflight)

    assert saved.task_id == preflight.task_id
    assert saved.plan == preflight.plan
    assert saved.decision == preflight.decision
    assert saved.blocking_reasons == preflight.blocking_reasons
    assert saved.warnings == preflight.warnings
    assert saved.checked_at == preflight.checked_at


def test_json_store_round_trips_stored_data():
    plan = _plan()
    checked_at = datetime(2026, 3, 1, tzinfo=timezone.utc)
    preflight = _preflight_result(
        plan=plan, decision=DENY, blocking_reasons=("a violation",), warnings=("a warning",), checked_at=checked_at
    )

    with tempfile.TemporaryDirectory() as tmp_dir:
        path = Path(tmp_dir) / "preflights.json"
        store = LLMAgentTaskRecoveryPreflightStore(store=JsonAgentTaskRecoveryPreflightStore(path))

        saved = store.save(preflight)
        reloaded_store = LLMAgentTaskRecoveryPreflightStore(store=JsonAgentTaskRecoveryPreflightStore(path))
        fetched = reloaded_store.get("task-1")

        assert fetched == saved
        assert fetched.plan == plan
        assert fetched.blocking_reasons == ("a violation",)
        assert fetched.warnings == ("a warning",)
        assert fetched.checked_at == checked_at
