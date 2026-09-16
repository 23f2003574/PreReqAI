from datetime import datetime, timedelta, timezone

import pytest

from backend.agent_task_dependencies import LLMAgentTaskDependencyService
from backend.agent_task_dependency_resolution import LLMAgentTaskDependencyResolver
from backend.agent_task_event_analytics import (
    LLMAgentTaskEventFailureClassifier,
    LLMAgentTaskEventFailureRecoveryPlanner,
)
from backend.agent_task_events import (
    DEPENDENCY_REMOVED,
    LIFECYCLE_TRANSITIONED,
    InMemoryAgentTaskEventStore,
    LLMAgentTaskEventQueryService,
    LLMAgentTaskEventReplayService,
    LLMAgentTaskEventService,
)
from backend.agent_task_lifecycle import (
    COMPLETED,
    FAILED,
    PLANNED,
    READY,
    RUNNING,
    LLMAgentTaskLifecycleService,
)
from backend.agent_task_queue_retry_eligibility import RetryEligibilityResult
from backend.agent_task_readiness import AgentTaskReadinessCheck, AgentTaskReadinessResult
from backend.agent_task_recovery_guardrails import (
    LLMAgentTaskRecoveryGuardEvaluationService,
    LLMAgentTaskRecoveryGuardService,
    LLMAgentTaskRecoveryPreflightApprovalService,
    LLMAgentTaskRecoveryPreflightAuthorizationService,
    LLMAgentTaskRecoveryPreflightAuthorizationValidationService,
    LLMAgentTaskRecoveryPreflightFreshnessService,
    LLMAgentTaskRecoveryPreflightInvalidationService,
    LLMAgentTaskRecoveryPreflightService,
    LLMAgentTaskRecoveryPreflightStore,
)
from backend.agent_task_recovery_schedule_dependencies import (
    InvalidAgentTaskRecoveryScheduleDependencyWakeError,
    LLMAgentTaskRecoveryPreflightScheduleDependencyBlockingService,
    LLMAgentTaskRecoveryPreflightScheduleDependencyReconciliationService,
    LLMAgentTaskRecoveryPreflightScheduleDependencyService,
    LLMAgentTaskRecoveryPreflightScheduleDependencyWakeService,
)
from backend.agent_task_recovery_scheduling import (
    CANCELLED,
    SCHEDULED,
    LLMAgentTaskRecoveryPreflightScheduleDispatchService,
    LLMAgentTaskRecoveryPreflightScheduleExpirationService,
    LLMAgentTaskRecoveryPreflightSchedulingService,
    LLMAgentTaskRecoveryPreflightScheduleValidationService,
)


class _FakeReadinessService:
    def __init__(self, policy_passed=True, dependencies_passed=True):
        self.set(policy_passed=policy_passed, dependencies_passed=dependencies_passed)

    def set(self, policy_passed=True, dependencies_passed=True):
        checks = [
            AgentTaskReadinessCheck(name="lifecycle_state", passed=True),
            AgentTaskReadinessCheck(
                name="dependencies", passed=dependencies_passed,
                detail=None if dependencies_passed else "dependency X is not yet resolved",
            ),
            AgentTaskReadinessCheck(
                name="policy", passed=policy_passed, detail=None if policy_passed else "policy denies task execution"
            ),
        ]
        blocking = [c.detail for c in checks if not c.passed and c.detail]
        self._result = AgentTaskReadinessResult(
            ready=not blocking, task_id="unused", blocking_reasons=blocking, warnings=[], checks=checks
        )

    def check(self, task_id):
        return self._result


class _FakeRetryEligibilityService:
    def __init__(self, eligible=True, reason="eligible"):
        self._result = RetryEligibilityResult(task_id="unused", eligible=eligible, reason=reason)

    def check(self, task_id):
        return self._result


class _FakeRetryScheduler:
    def get_retry_schedule(self, task_id):
        return None


class _FakeDeadLetterService:
    def get(self, task_id):
        return None


class _FakeReservationService:
    def is_reservation_valid(self, task_id):
        return False


def _definition(**overrides):
    definition = {"agent_id": "agent-1", "scope_id": "scope-1", "objective": "recover the task"}
    definition.update(overrides)
    return definition


def _task(lifecycle_service, **overrides):
    return lifecycle_service.create(_definition(**overrides))


def _advance_to(lifecycle_service, task, state):
    for target in (PLANNED, READY, RUNNING):
        if task.current_state == state:
            return task
        task = lifecycle_service.transition(task.task_id, target)
    return lifecycle_service.transition(task.task_id, state) if task.current_state != state else task


def _stack():
    store = InMemoryAgentTaskEventStore()
    event_service = LLMAgentTaskEventService(store=store)
    query_service = LLMAgentTaskEventQueryService(store=store)
    classifier = LLMAgentTaskEventFailureClassifier(query_service=query_service)
    replay_service = LLMAgentTaskEventReplayService(query_service=query_service)

    readiness = _FakeReadinessService()
    retry_eligibility = _FakeRetryEligibilityService()

    planner = LLMAgentTaskEventFailureRecoveryPlanner(
        classifier=classifier, readiness_service=readiness, retry_eligibility_service=retry_eligibility
    )
    guard = LLMAgentTaskRecoveryGuardService(
        classifier=classifier, replay_service=replay_service,
        readiness_service=readiness, retry_eligibility_service=retry_eligibility,
        retry_scheduler=_FakeRetryScheduler(), dead_letter_service=_FakeDeadLetterService(),
        reservation_service=_FakeReservationService(),
    )
    evaluation_service = LLMAgentTaskRecoveryGuardEvaluationService(guard_service=guard)
    preflight_service = LLMAgentTaskRecoveryPreflightService(planner=planner, evaluation_service=evaluation_service)
    preflight_store = LLMAgentTaskRecoveryPreflightStore()
    freshness_service = LLMAgentTaskRecoveryPreflightFreshnessService(
        preflight_store=preflight_store, classifier=classifier, replay_service=replay_service,
        readiness_service=readiness, retry_eligibility_service=retry_eligibility,
    )
    invalidation_service = LLMAgentTaskRecoveryPreflightInvalidationService(
        preflight_store=preflight_store, freshness_service=freshness_service
    )
    approval_service = LLMAgentTaskRecoveryPreflightApprovalService(
        preflight_store=preflight_store, invalidation_service=invalidation_service
    )
    authorization_service = LLMAgentTaskRecoveryPreflightAuthorizationService(
        preflight_store=preflight_store, approval_service=approval_service,
        invalidation_service=invalidation_service, evaluation_service=evaluation_service,
    )
    authorization_validation_service = LLMAgentTaskRecoveryPreflightAuthorizationValidationService(
        authorization_service=authorization_service, preflight_store=preflight_store,
        invalidation_service=invalidation_service, freshness_service=freshness_service,
        approval_service=approval_service, evaluation_service=evaluation_service,
    )
    scheduling_service = LLMAgentTaskRecoveryPreflightSchedulingService(
        approval_service=approval_service, authorization_service=authorization_service,
        validation_service=authorization_validation_service,
    )
    plain_validation_service = LLMAgentTaskRecoveryPreflightScheduleValidationService(
        scheduling_service=scheduling_service, authorization_validation_service=authorization_validation_service,
    )
    expiration_service = LLMAgentTaskRecoveryPreflightScheduleExpirationService(scheduling_service=scheduling_service)
    dispatch_service = LLMAgentTaskRecoveryPreflightScheduleDispatchService(
        validation_service=plain_validation_service, scheduling_service=scheduling_service,
    )

    lifecycle_service = LLMAgentTaskLifecycleService()
    dependency_service = LLMAgentTaskDependencyService(lifecycle_service)
    dependency_resolver = LLMAgentTaskDependencyResolver(lifecycle_service, dependency_service)
    gate_service = LLMAgentTaskRecoveryPreflightScheduleDependencyService(
        scheduling_service=scheduling_service, dependency_resolver=dependency_resolver
    )
    reconciliation_service = LLMAgentTaskRecoveryPreflightScheduleDependencyReconciliationService(
        scheduling_service=scheduling_service, dependency_service=gate_service, dependency_resolver=dependency_resolver
    )
    blocking_service = LLMAgentTaskRecoveryPreflightScheduleDependencyBlockingService(
        dependency_service=gate_service, scheduling_service=scheduling_service,
        validation_service=plain_validation_service, expiration_service=expiration_service,
    )
    wake_service = LLMAgentTaskRecoveryPreflightScheduleDependencyWakeService(
        reconciliation_service=reconciliation_service, scheduling_service=scheduling_service,
        validation_service=plain_validation_service, expiration_service=expiration_service,
        blocking_service=blocking_service, event_query_service=query_service,
    )

    lifecycle_service.create(_definition(task_id="task-1"))

    return {
        "event_service": event_service,
        "query_service": query_service,
        "preflight_service": preflight_service,
        "preflight_store": preflight_store,
        "approval_service": approval_service,
        "authorization_service": authorization_service,
        "scheduling_service": scheduling_service,
        "lifecycle_service": lifecycle_service,
        "dependency_service": dependency_service,
        "gate_service": gate_service,
        "reconciliation_service": reconciliation_service,
        "blocking_service": blocking_service,
        "validation_service": plain_validation_service,
        "expiration_service": expiration_service,
        "dispatch_service": dispatch_service,
        "wake_service": wake_service,
    }


def _fail_task(event_service, task_id="task-1"):
    event_service.emit(task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})
    return event_service.emit(task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": FAILED})


def _scheduled(s, task_id="task-1", execute_at=None):
    preflight = s["preflight_store"].save(s["preflight_service"].run(task_id))
    s["approval_service"].request(task_id, preflight.preflight_id)
    s["approval_service"].approve(task_id, preflight.preflight_id, actor="alice")
    schedule = s["scheduling_service"].schedule(task_id, preflight.preflight_id, execute_at=execute_at)
    return preflight, schedule


def _blocked_schedule(s, dep, task_id="task-1", execute_at=None):
    """A schedule durably blocked (Commit #3) on dep, deferred (Commit
    #4-style) to execute_at."""
    s["dependency_service"].add_dependency(task_id, dep.task_id)
    _fail_task(s["event_service"], task_id)
    _, schedule = _scheduled(s, task_id=task_id, execute_at=execute_at)
    s["blocking_service"].block(task_id, schedule.schedule_id, (dep.task_id,), "waiting on dep")
    return schedule


# --- dependency resolution wakes a schedule -------------------------------------------------


def test_wake_schedule_wakes_once_dependency_resolves():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _blocked_schedule(s, dep, execute_at=datetime.now(timezone.utc) + timedelta(hours=1))

    _advance_to(s["lifecycle_service"], dep, COMPLETED)
    outcome = s["wake_service"].wake_schedule("task-1", schedule.schedule_id)

    assert outcome.woken is True
    assert outcome.already_awake is False
    assert outcome.schedule_id != schedule.schedule_id
    assert outcome.previous_schedule_id == schedule.schedule_id

    new_record = s["scheduling_service"].get("task-1", outcome.schedule_id)
    assert new_record.status == SCHEDULED
    assert new_record.execute_at is None


def test_woken_schedule_is_not_durably_blocked():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _blocked_schedule(s, dep, execute_at=datetime.now(timezone.utc) + timedelta(hours=1))

    _advance_to(s["lifecycle_service"], dep, COMPLETED)
    outcome = s["wake_service"].wake_schedule("task-1", schedule.schedule_id)

    # The original schedule_id's own Commit #3 block record is left
    # exactly as it was (inert history, tied to a now-cancelled
    # schedule) -- the NEW schedule_id wake() created has never been
    # blocked at all, so it reads as not-blocked without any explicit
    # unblock() call.
    assert s["blocking_service"].get_latest("task-1", schedule.schedule_id).status == "blocked"
    assert s["blocking_service"].get_latest("task-1", outcome.schedule_id) is None
    status = s["blocking_service"].status("task-1", outcome.schedule_id)
    assert status.currently_blocked is False


# --- dependency still blocked ---------------------------------------------------------------


def test_wake_schedule_preserves_when_still_blocked():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _blocked_schedule(s, dep, execute_at=datetime.now(timezone.utc) + timedelta(hours=1))

    outcome = s["wake_service"].wake_schedule("task-1", schedule.schedule_id)

    assert outcome.woken is False
    assert outcome.schedule_id == schedule.schedule_id
    assert "not ready" in outcome.reason


# --- multiple waiting schedules -------------------------------------------------------------


def test_wake_wakes_multiple_schedules_and_preserves_others():
    # Two independent tasks, each with its own single waiting schedule --
    # a task's dependency graph (and, in this test harness, the guard/
    # preflight pipeline's own "one active preflight at a time" behavior)
    # is scoped to task_id, so "multiple waiting schedules" is naturally
    # demonstrated across tasks rather than within one.
    s = _stack()
    s["lifecycle_service"].create(_definition(task_id="task-2"))
    dep_a = _task(s["lifecycle_service"])
    dep_b = _task(s["lifecycle_service"])
    schedule_a = _blocked_schedule(s, dep_a, task_id="task-1", execute_at=datetime.now(timezone.utc) + timedelta(hours=1))
    schedule_b = _blocked_schedule(s, dep_b, task_id="task-2", execute_at=datetime.now(timezone.utc) + timedelta(hours=1))

    _advance_to(s["lifecycle_service"], dep_a, COMPLETED)
    # dep_b stays pending.

    result_1 = s["wake_service"].wake("task-1")
    result_2 = s["wake_service"].wake("task-2")

    assert len(result_1.woken) == 1
    assert result_1.woken[0].previous_schedule_id == schedule_a.schedule_id
    assert len(result_2.preserved) == 1
    assert result_2.preserved[0].schedule_id == schedule_b.schedule_id


def test_wake_with_dependency_id_filters_out_unrelated_dependency():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    # Commit #3's own block record's own `dependencies` (the caller's
    # asserted evidence at block() time) is what dependency_id filtering
    # actually matches against.
    schedule = _blocked_schedule(s, dep, execute_at=datetime.now(timezone.utc) + timedelta(hours=1))
    s["blocking_service"].get_latest("task-1", schedule.schedule_id)  # sanity: a block record exists

    unrelated_result = s["wake_service"].wake("task-1", dependency_id="some-other-dependency")
    assert unrelated_result.outcomes == ()

    matching_result = s["wake_service"].wake("task-1", dependency_id=dep.task_id)
    assert len(matching_result.outcomes) == 1
    assert matching_result.outcomes[0].previous_schedule_id == schedule.schedule_id


# --- stale / expired / cancelled schedules --------------------------------------------------


def test_wake_schedule_rejects_cancelled_schedule():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _blocked_schedule(s, dep, execute_at=datetime.now(timezone.utc) + timedelta(hours=1))
    _advance_to(s["lifecycle_service"], dep, COMPLETED)
    s["scheduling_service"].cancel("task-1", schedule.schedule_id, reason="no longer needed")

    outcome = s["wake_service"].wake_schedule("task-1", schedule.schedule_id)

    assert outcome.woken is False
    assert "cancelled" in outcome.reason


def test_wake_schedule_rejects_revoked_authorization():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _blocked_schedule(s, dep, execute_at=datetime.now(timezone.utc) + timedelta(hours=1))
    _advance_to(s["lifecycle_service"], dep, COMPLETED)
    s["authorization_service"].revoke("task-1", schedule.authorization_id, reason="revoked externally")

    outcome = s["wake_service"].wake_schedule("task-1", schedule.schedule_id)

    assert outcome.woken is False
    assert "revoked" in outcome.reason


def test_wake_schedule_rejects_expired_schedule():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    past = datetime.now(timezone.utc) - timedelta(hours=2)
    schedule = _blocked_schedule(s, dep, execute_at=past)
    _advance_to(s["lifecycle_service"], dep, COMPLETED)

    short_expiration_service = LLMAgentTaskRecoveryPreflightScheduleExpirationService(
        scheduling_service=s["scheduling_service"], max_overdue_age=timedelta(0)
    )
    wake_service = LLMAgentTaskRecoveryPreflightScheduleDependencyWakeService(
        reconciliation_service=s["reconciliation_service"], scheduling_service=s["scheduling_service"],
        validation_service=s["validation_service"], expiration_service=short_expiration_service,
    )

    outcome = wake_service.wake_schedule("task-1", schedule.schedule_id)

    assert outcome.woken is False
    assert "expiration window" in outcome.reason


# --- duplicate wake-up / idempotent ----------------------------------------------------------


def test_repeated_wake_is_idempotent_and_avoids_duplicates():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _blocked_schedule(s, dep, execute_at=datetime.now(timezone.utc) + timedelta(hours=1))
    _advance_to(s["lifecycle_service"], dep, COMPLETED)

    first = s["wake_service"].wake_schedule("task-1", schedule.schedule_id)
    second = s["wake_service"].wake_schedule("task-1", first.schedule_id)

    assert first.woken is True
    assert first.already_awake is False
    assert second.woken is True
    assert second.already_awake is True
    assert second.schedule_id == first.schedule_id

    records = s["scheduling_service"].list("task-1")
    assert sum(1 for r in records if r.status == SCHEDULED) == 1
    assert len(s["wake_service"].get_history("task-1")) == 1


# --- event integration -------------------------------------------------------------------------


def test_wake_result_correlates_with_dependency_change_event():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _blocked_schedule(s, dep, execute_at=datetime.now(timezone.utc) + timedelta(hours=1))
    _advance_to(s["lifecycle_service"], dep, COMPLETED)
    dependency_event = s["event_service"].emit(
        "task-1", DEPENDENCY_REMOVED, payload={"dependency_task_id": dep.task_id}
    )

    result = s["wake_service"].wake("task-1")

    assert result.triggering_event_id == dependency_event.event_id


def test_wake_works_without_event_query_service():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _blocked_schedule(s, dep, execute_at=datetime.now(timezone.utc) + timedelta(hours=1))
    _advance_to(s["lifecycle_service"], dep, COMPLETED)

    wake_service = LLMAgentTaskRecoveryPreflightScheduleDependencyWakeService(
        reconciliation_service=s["reconciliation_service"], scheduling_service=s["scheduling_service"],
        validation_service=s["validation_service"], expiration_service=s["expiration_service"],
        blocking_service=s["blocking_service"],
    )

    result = wake_service.wake("task-1")

    assert result.triggering_event_id is None
    assert len(result.woken) == 1


# --- normal dispatch eligibility after wake-up ------------------------------------------------


def test_dispatch_succeeds_after_wake_up():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _blocked_schedule(s, dep, execute_at=datetime.now(timezone.utc) + timedelta(hours=1))
    _advance_to(s["lifecycle_service"], dep, COMPLETED)

    outcome = s["wake_service"].wake_schedule("task-1", schedule.schedule_id)

    validation = s["validation_service"].validate("task-1", outcome.schedule_id)
    assert validation.valid is True
    dispatch = s["dispatch_service"].dispatch("task-1", outcome.schedule_id)
    assert dispatch.status == "dispatched"


# --- history preservation ---------------------------------------------------------------------


def test_wake_history_preserved():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _blocked_schedule(s, dep, execute_at=datetime.now(timezone.utc) + timedelta(hours=1))
    _advance_to(s["lifecycle_service"], dep, COMPLETED)

    outcome = s["wake_service"].wake_schedule("task-1", schedule.schedule_id)

    history = s["wake_service"].get_history("task-1")
    assert len(history) == 1
    assert history[0].previous_schedule_id == schedule.schedule_id
    assert history[0].schedule_id == outcome.schedule_id


# --- argument validation -----------------------------------------------------------------------


def test_wake_rejects_blank_arguments():
    s = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryScheduleDependencyWakeError):
        s["wake_service"].wake("")
    with pytest.raises(InvalidAgentTaskRecoveryScheduleDependencyWakeError):
        s["wake_service"].wake("task-1", dependency_id="")
    with pytest.raises(InvalidAgentTaskRecoveryScheduleDependencyWakeError):
        s["wake_service"].wake_schedule("task-1", "")


def test_wake_schedule_rejects_unknown_schedule():
    s = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryScheduleDependencyWakeError):
        s["wake_service"].wake_schedule("task-1", "never-existed")


def test_wake_on_task_with_no_schedules_is_empty():
    s = _stack()
    result = s["wake_service"].wake("task-1")
    assert result.outcomes == ()
    assert result.woken == ()
    assert result.preserved == ()
