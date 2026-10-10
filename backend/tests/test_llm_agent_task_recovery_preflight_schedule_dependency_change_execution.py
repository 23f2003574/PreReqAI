from datetime import datetime, timedelta, timezone

import pytest

from backend.agent_task_dependencies import LLMAgentTaskDependencyService
from backend.agent_task_dependency_resolution import LLMAgentTaskDependencyResolver
from backend.agent_task_event_analytics import (
    LLMAgentTaskEventFailureClassifier,
    LLMAgentTaskEventFailureRecoveryPlanner,
)
from backend.agent_task_events import (
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
from backend.agent_task_queue_retry_eligibility import RetryEligibilityResult
from backend.agent_task_recovery_schedule_dependencies import (
    ACTION_ESCALATE,
    ACTION_EXPIRE,
    ACTION_NO_OP,
    ACTION_REVALIDATE,
    ACTION_WAIT,
    APPLICATION_FAILED,
    APPLIED,
    REJECTED,
    InvalidAgentTaskRecoveryScheduleDependencyChangeError,
    LLMAgentTaskRecoveryPreflightScheduleDependencyBlockingService,
    LLMAgentTaskRecoveryPreflightScheduleDependencyChangePlanner,
    LLMAgentTaskRecoveryPreflightScheduleDependencyChangeService,
    LLMAgentTaskRecoveryPreflightScheduleDependencyEscalationResolutionService,
    LLMAgentTaskRecoveryPreflightScheduleDependencyEscalationService,
    LLMAgentTaskRecoveryPreflightScheduleDependencyImpactService,
    LLMAgentTaskRecoveryPreflightScheduleDependencyReconciliationService,
    LLMAgentTaskRecoveryPreflightScheduleDependencyService,
    LLMAgentTaskRecoveryPreflightScheduleDependencyTimeoutService,
    LLMAgentTaskRecoveryPreflightScheduleDependencyWaitService,
    LLMAgentTaskRecoveryPreflightScheduleDependencyWakeService,
)
from backend.agent_task_recovery_scheduling import (
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


class _FlakyWaitService:
    """Wraps a real wait_service, raising unexpectedly for one specific
    schedule_id -- used to simulate a genuine mid-batch execution
    failure."""

    def __init__(self, real_wait_service, fails_for_schedule_id):
        self._real = real_wait_service
        self._fails_for = fails_for_schedule_id

    def plan_wait(self, task_id, schedule_id, now=None):
        if schedule_id == self._fails_for:
            raise RuntimeError("simulated transient failure")
        return self._real.plan_wait(task_id, schedule_id, now=now)

    def apply_wait(self, task_id, schedule_id, wait_plan, now=None):
        return self._real.apply_wait(task_id, schedule_id, wait_plan, now=now)


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
    timeout_service = LLMAgentTaskRecoveryPreflightScheduleDependencyTimeoutService(
        dependency_service=gate_service, scheduling_service=scheduling_service,
        blocking_service=blocking_service, expiration_service=expiration_service,
        max_wait_duration=timedelta(hours=1),
    )
    escalation_service = LLMAgentTaskRecoveryPreflightScheduleDependencyEscalationService(
        timeout_service=timeout_service, scheduling_service=scheduling_service,
    )
    wake_service = LLMAgentTaskRecoveryPreflightScheduleDependencyWakeService(
        reconciliation_service=reconciliation_service, scheduling_service=scheduling_service,
        validation_service=plain_validation_service, expiration_service=expiration_service,
        blocking_service=blocking_service,
    )
    escalation_resolution_service = LLMAgentTaskRecoveryPreflightScheduleDependencyEscalationResolutionService(
        escalation_service=escalation_service, wake_service=wake_service,
        reconciliation_service=reconciliation_service, scheduling_service=scheduling_service,
    )
    wait_service = LLMAgentTaskRecoveryPreflightScheduleDependencyWaitService(
        dependency_service=gate_service, scheduling_service=scheduling_service,
        validation_service=plain_validation_service, expiration_service=expiration_service,
    )
    impact_service = LLMAgentTaskRecoveryPreflightScheduleDependencyImpactService(
        reconciliation_service=reconciliation_service, scheduling_service=scheduling_service,
        timeout_service=timeout_service,
    )
    planner_service = LLMAgentTaskRecoveryPreflightScheduleDependencyChangePlanner(
        impact_service=impact_service, scheduling_service=scheduling_service,
        escalation_service=escalation_service, escalation_resolution_service=escalation_resolution_service,
    )
    change_service = LLMAgentTaskRecoveryPreflightScheduleDependencyChangeService(
        planner_service=planner_service, scheduling_service=scheduling_service,
        wait_service=wait_service, wake_service=wake_service,
        escalation_service=escalation_service, timeout_service=timeout_service,
    )

    return {
        "event_service": event_service,
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
        "timeout_service": timeout_service,
        "escalation_service": escalation_service,
        "escalation_resolution_service": escalation_resolution_service,
        "wake_service": wake_service,
        "wait_service": wait_service,
        "impact_service": impact_service,
        "planner_service": planner_service,
        "change_service": change_service,
        "dispatch_service": dispatch_service,
        "validation_service": plain_validation_service,
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


_DEFERRED = object()  # sentinel: "use the default +6h deferral" -- distinct
# from an explicit execute_at=None (immediately due), which callers that
# need a genuinely due schedule (e.g. for plan_wait()'s own real-wall-clock
# validate() call) must pass explicitly.


def _task_with_schedule(s, task_id, dep, execute_at=_DEFERRED):
    s["lifecycle_service"].create(_definition(task_id=task_id))
    s["dependency_service"].add_dependency(task_id, dep.task_id)
    _fail_task(s["event_service"], task_id)
    if execute_at is _DEFERRED:
        execute_at = datetime.now(timezone.utc) + timedelta(hours=6)
    _, schedule = _scheduled(s, task_id=task_id, execute_at=execute_at)
    return schedule


# --- each supported action --------------------------------------------------------------------


def test_apply_schedule_no_op():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    _advance_to(s["lifecycle_service"], dep, COMPLETED)
    schedule = _task_with_schedule(s, "task-1", dep)
    s["planner_service"].plan("task-1", schedule_id=schedule.schedule_id)  # baseline reconciliation

    result = s["change_service"].apply_schedule("task-1", schedule.schedule_id, ACTION_NO_OP)

    assert result.status == APPLIED
    assert result.new_schedule_id == schedule.schedule_id
    assert s["scheduling_service"].get("task-1", schedule.schedule_id).status == "scheduled"


def test_apply_schedule_revalidate():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _task_with_schedule(s, "task-1", dep)
    s["planner_service"].plan("task-1", schedule_id=schedule.schedule_id)  # baseline, still pending
    _advance_to(s["lifecycle_service"], dep, COMPLETED)

    result = s["change_service"].apply_schedule("task-1", schedule.schedule_id, ACTION_REVALIDATE)

    assert result.status == APPLIED
    assert result.new_schedule_id != schedule.schedule_id
    new_record = s["scheduling_service"].get("task-1", result.new_schedule_id)
    assert new_record.status == "scheduled"
    assert new_record.execute_at is None


def test_apply_schedule_wait():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _task_with_schedule(s, "task-1", dep, execute_at=None)

    result = s["change_service"].apply_schedule("task-1", schedule.schedule_id, ACTION_WAIT)

    assert result.status == APPLIED
    assert result.new_schedule_id != schedule.schedule_id
    new_record = s["scheduling_service"].get("task-1", result.new_schedule_id)
    assert new_record.execute_at is not None
    assert new_record.execute_at > datetime.now(timezone.utc)


def test_apply_schedule_escalate():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _task_with_schedule(s, "task-1", dep)
    far_future = datetime.now(timezone.utc) + timedelta(hours=2)

    result = s["change_service"].apply_schedule("task-1", schedule.schedule_id, ACTION_ESCALATE, now=far_future)

    assert result.status == APPLIED
    assert result.new_schedule_id == schedule.schedule_id
    assert len(s["escalation_service"].get_history("task-1", schedule.schedule_id)) == 1


def test_apply_schedule_expire_via_direct_cancel():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _task_with_schedule(s, "task-1", dep)
    _advance_to(s["lifecycle_service"], dep, FAILED)

    result = s["change_service"].apply_schedule("task-1", schedule.schedule_id, ACTION_EXPIRE)

    assert result.status == APPLIED
    assert s["scheduling_service"].get("task-1", schedule.schedule_id).status == "cancelled"


def test_apply_schedule_expire_via_timeout_service():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _task_with_schedule(s, "task-1", dep)
    far_future = datetime.now(timezone.utc) + timedelta(hours=2)
    _advance_to(s["lifecycle_service"], dep, FAILED)

    result = s["change_service"].apply_schedule("task-1", schedule.schedule_id, ACTION_EXPIRE, now=far_future)

    assert result.status == APPLIED
    cancelled = s["scheduling_service"].get("task-1", schedule.schedule_id)
    assert cancelled.status == "cancelled"


# --- stale plans ------------------------------------------------------------------------------


def test_stale_plan_rejected():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _task_with_schedule(s, "task-1", dep)

    plan = s["planner_service"].plan("task-1", schedule_id=schedule.schedule_id)
    assert plan.items[0].action == ACTION_WAIT
    _advance_to(s["lifecycle_service"], dep, COMPLETED)  # dependency resolved after planning

    result = s["change_service"].apply_schedule("task-1", schedule.schedule_id, ACTION_WAIT)

    assert result.status == REJECTED
    assert "stale" in result.reason
    # Nothing was actually applied.
    assert s["scheduling_service"].get("task-1", schedule.schedule_id).status == "scheduled"


# --- conflicting plans --------------------------------------------------------------------------


def test_conflicting_plan_rejected():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _task_with_schedule(s, "task-1", dep)
    far_future = datetime.now(timezone.utc) + timedelta(hours=2)
    s["planner_service"].plan("task-1", schedule_id=schedule.schedule_id)  # baseline, still pending
    s["escalation_service"].escalate("task-1", schedule.schedule_id, now=far_future)
    _advance_to(s["lifecycle_service"], dep, COMPLETED)

    result = s["change_service"].apply_schedule("task-1", schedule.schedule_id, ACTION_REVALIDATE, now=far_future)

    assert result.status == REJECTED
    assert "conflicting" in result.reason
    assert s["scheduling_service"].get("task-1", schedule.schedule_id).status == "scheduled"


# --- already-applied actions --------------------------------------------------------------------


def test_repeated_wait_application_is_idempotent():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _task_with_schedule(s, "task-1", dep, execute_at=None)

    first = s["change_service"].apply_schedule("task-1", schedule.schedule_id, ACTION_WAIT)
    # A second call for the SAME still-deferred schedule (the one
    # WAIT actually left behind) is a genuine no-op, never a duplicate
    # deferral -- calling it again on the now-superseded ORIGINAL
    # schedule_id would instead be correctly rejected as stale (same
    # as revalidate; see test_repeated_revalidate_is_rejected_as_stale_
    # the_second_time).
    second = s["change_service"].apply_schedule("task-1", first.new_schedule_id, ACTION_WAIT)

    assert first.status == second.status == APPLIED
    assert second.new_schedule_id == first.new_schedule_id
    assert sum(1 for r in s["scheduling_service"].list("task-1") if r.status == "scheduled") == 1


def test_repeated_escalate_application_is_idempotent():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _task_with_schedule(s, "task-1", dep)
    far_future = datetime.now(timezone.utc) + timedelta(hours=2)

    first = s["change_service"].apply_schedule("task-1", schedule.schedule_id, ACTION_ESCALATE, now=far_future)
    second = s["change_service"].apply_schedule("task-1", schedule.schedule_id, ACTION_ESCALATE, now=far_future)

    assert first.status == second.status == APPLIED
    assert len(s["escalation_service"].get_history("task-1", schedule.schedule_id)) == 1


def test_repeated_revalidate_is_rejected_as_stale_the_second_time():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _task_with_schedule(s, "task-1", dep)
    s["planner_service"].plan("task-1", schedule_id=schedule.schedule_id)  # baseline, still pending
    _advance_to(s["lifecycle_service"], dep, COMPLETED)

    first = s["change_service"].apply_schedule("task-1", schedule.schedule_id, ACTION_REVALIDATE)
    # Same (original) schedule_id, same action -- but it was already
    # superseded by the first call, so this is now stale, not a silent
    # duplicate.
    second = s["change_service"].apply_schedule("task-1", schedule.schedule_id, ACTION_REVALIDATE)

    assert first.status == APPLIED
    assert second.status == REJECTED
    assert "stale" in second.reason


# --- multiple schedules -----------------------------------------------------------------------------


def test_apply_covers_multiple_schedules_in_one_batch():
    # Same reliable technique as Commit #10's own ordering test: block +
    # wait creates a second, genuinely independent schedule record for
    # the SAME task (the first one now cancelled/superseded), giving one
    # plan with two real items to apply together.
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule_a = _task_with_schedule(s, "task-1", dep, execute_at=None)
    s["blocking_service"].block("task-1", schedule_a.schedule_id, (dep.task_id,), "waiting on dep")
    wait_plan = s["wait_service"].plan_wait("task-1", schedule_a.schedule_id)
    schedule_b = s["wait_service"].apply_wait("task-1", schedule_a.schedule_id, wait_plan)

    plan = s["planner_service"].plan("task-1")
    assert len(plan.items) == 2

    result = s["change_service"].apply("task-1", plan)

    assert len(result.results) == 2
    results_by_schedule = {r.schedule_id: r for r in result.results}
    assert results_by_schedule[schedule_a.schedule_id].status == APPLIED
    assert results_by_schedule[schedule_a.schedule_id].action == ACTION_EXPIRE
    assert results_by_schedule[schedule_b.schedule_id].status == APPLIED
    assert results_by_schedule[schedule_b.schedule_id].action == ACTION_WAIT


# --- failure midway through a plan -----------------------------------------------------------------------


def test_apply_schedule_directly_propagates_an_unexpected_failure():
    # apply_schedule() itself never swallows an unexpected exception --
    # only apply()'s own batch loop does (Rule: "failure midway through
    # A PLAN" is about a batch, not a single direct call).
    s = _stack()
    dep_a = _task(s["lifecycle_service"])
    schedule_a = _task_with_schedule(s, "task-1", dep_a, execute_at=None)

    flaky_wait_service = _FlakyWaitService(s["wait_service"], fails_for_schedule_id=schedule_a.schedule_id)
    change_service = LLMAgentTaskRecoveryPreflightScheduleDependencyChangeService(
        planner_service=s["planner_service"], scheduling_service=s["scheduling_service"],
        wait_service=flaky_wait_service, wake_service=s["wake_service"],
        escalation_service=s["escalation_service"], timeout_service=s["timeout_service"],
    )

    with pytest.raises(RuntimeError, match="simulated transient failure"):
        change_service.apply_schedule("task-1", schedule_a.schedule_id, ACTION_WAIT)

    # A second, independent task's own schedule is completely unaffected.
    dep_b = _task(s["lifecycle_service"])
    schedule_b = _task_with_schedule(s, "task-2", dep_b, execute_at=None)
    result_b = change_service.apply_schedule("task-2", schedule_b.schedule_id, ACTION_WAIT)
    assert result_b.status == APPLIED


def test_apply_batch_continues_after_one_item_fails():
    s = _stack()
    dep_a = _task(s["lifecycle_service"])
    schedule_a = _task_with_schedule(s, "task-1", dep_a, execute_at=None)

    flaky_wait_service = _FlakyWaitService(s["wait_service"], fails_for_schedule_id=schedule_a.schedule_id)
    change_service = LLMAgentTaskRecoveryPreflightScheduleDependencyChangeService(
        planner_service=s["planner_service"], scheduling_service=s["scheduling_service"],
        wait_service=flaky_wait_service, wake_service=s["wake_service"],
        escalation_service=s["escalation_service"], timeout_service=s["timeout_service"],
    )

    plan = s["planner_service"].plan("task-1")
    result = change_service.apply("task-1", plan)

    assert len(result.results) == 1
    assert result.results[0].status == APPLICATION_FAILED
    assert "simulated transient failure" in result.results[0].reason


# --- history preservation --------------------------------------------------------------------------


def test_apply_preserves_dependency_and_blocking_history():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _task_with_schedule(s, "task-1", dep)
    s["blocking_service"].block("task-1", schedule.schedule_id, (dep.task_id,), "waiting on dep")
    blocking_history_before = s["blocking_service"].get_history("task-1", schedule.schedule_id)

    far_future = datetime.now(timezone.utc) + timedelta(hours=2)
    s["change_service"].apply_schedule("task-1", schedule.schedule_id, ACTION_ESCALATE, now=far_future)

    assert s["blocking_service"].get_history("task-1", schedule.schedule_id) == blocking_history_before
    assert s["lifecycle_service"].get(dep.task_id).current_state == "created"


# --- proof recovery execution is never triggered ---------------------------------------------------------


def test_recovery_execution_never_triggered():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _task_with_schedule(s, "task-1", dep)
    s["planner_service"].plan("task-1", schedule_id=schedule.schedule_id)  # baseline
    _advance_to(s["lifecycle_service"], dep, COMPLETED)

    result = s["change_service"].apply_schedule("task-1", schedule.schedule_id, ACTION_REVALIDATE)

    assert s["dispatch_service"].list("task-1") == []
    validation = s["validation_service"].validate("task-1", result.new_schedule_id)
    assert validation.valid is True
    dispatched = s["dispatch_service"].dispatch("task-1", result.new_schedule_id)
    assert dispatched.status == "dispatched"


# --- argument validation -----------------------------------------------------------------------------------


def test_apply_schedule_rejects_invalid_action():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _task_with_schedule(s, "task-1", dep)
    with pytest.raises(InvalidAgentTaskRecoveryScheduleDependencyChangeError):
        s["change_service"].apply_schedule("task-1", schedule.schedule_id, "not-a-real-action")


def test_apply_rejects_non_plan_object():
    s = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryScheduleDependencyChangeError):
        s["change_service"].apply("task-1", "not-a-plan")


def test_apply_rejects_task_id_mismatch():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _task_with_schedule(s, "task-1", dep)
    plan = s["planner_service"].plan("task-1", schedule_id=schedule.schedule_id)
    with pytest.raises(InvalidAgentTaskRecoveryScheduleDependencyChangeError):
        s["change_service"].apply("task-2", plan)
