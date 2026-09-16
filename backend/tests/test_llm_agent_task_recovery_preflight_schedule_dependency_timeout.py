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
    NOT_WAITING,
    TIMED_OUT,
    TIMEOUT_ACTIVE,
    TIMEOUT_NOT_APPLICABLE,
    InvalidAgentTaskRecoveryScheduleDependencyTimeoutError,
    LLMAgentTaskRecoveryPreflightScheduleDependencyBlockingService,
    LLMAgentTaskRecoveryPreflightScheduleDependencyService,
    LLMAgentTaskRecoveryPreflightScheduleDependencyTimeoutService,
)
from backend.agent_task_recovery_scheduling import (
    InvalidAgentTaskRecoveryScheduleDispatchError,
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
    blocking_service = LLMAgentTaskRecoveryPreflightScheduleDependencyBlockingService(
        dependency_service=gate_service, scheduling_service=scheduling_service,
        validation_service=plain_validation_service, expiration_service=expiration_service,
    )
    timeout_service = LLMAgentTaskRecoveryPreflightScheduleDependencyTimeoutService(
        dependency_service=gate_service, scheduling_service=scheduling_service,
        blocking_service=blocking_service, expiration_service=expiration_service,
        dispatch_service=dispatch_service, max_wait_duration=timedelta(hours=1),
    )
    timeout_wired_validation_service = LLMAgentTaskRecoveryPreflightScheduleValidationService(
        scheduling_service=scheduling_service, authorization_validation_service=authorization_validation_service,
        dependency_service=timeout_service,
    )
    timeout_wired_dispatch_service = LLMAgentTaskRecoveryPreflightScheduleDispatchService(
        validation_service=timeout_wired_validation_service, scheduling_service=scheduling_service,
    )

    lifecycle_service.create(_definition(task_id="task-1"))

    return {
        "event_service": event_service,
        "preflight_service": preflight_service,
        "preflight_store": preflight_store,
        "approval_service": approval_service,
        "scheduling_service": scheduling_service,
        "lifecycle_service": lifecycle_service,
        "dependency_service": dependency_service,
        "gate_service": gate_service,
        "blocking_service": blocking_service,
        "authorization_validation_service": authorization_validation_service,
        "validation_service": plain_validation_service,
        "expiration_service": expiration_service,
        "dispatch_service": dispatch_service,
        "timeout_service": timeout_service,
        "timeout_wired_validation_service": timeout_wired_validation_service,
        "timeout_wired_dispatch_service": timeout_wired_dispatch_service,
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


def _blocked_schedule(s, dep, task_id="task-1"):
    s["dependency_service"].add_dependency(task_id, dep.task_id)
    _fail_task(s["event_service"], task_id)
    _, schedule = _scheduled(s, task_id=task_id, execute_at=datetime.now(timezone.utc) + timedelta(hours=2))
    s["blocking_service"].block(task_id, schedule.schedule_id, (dep.task_id,), "waiting on dep")
    return schedule


# --- active wait -----------------------------------------------------------------------------


def test_active_wait_reports_active():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _blocked_schedule(s, dep)

    result = s["timeout_service"].check("task-1", schedule.schedule_id)

    assert result.state == TIMEOUT_ACTIVE
    assert result.ready is False
    assert result.timed_out is False
    assert result.deadline is not None
    assert result.wait_started_at is not None


# --- exact deadline boundary -------------------------------------------------------------------


def test_exact_deadline_boundary_is_timed_out():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _blocked_schedule(s, dep)
    block_record = s["blocking_service"].get_latest("task-1", schedule.schedule_id)
    deadline = block_record.occurred_at + timedelta(hours=1)

    just_before = s["timeout_service"].check("task-1", schedule.schedule_id, now=deadline - timedelta(microseconds=1))
    assert just_before.state == TIMEOUT_ACTIVE

    at_deadline = s["timeout_service"].check("task-1", schedule.schedule_id, now=deadline)
    assert at_deadline.state == TIMED_OUT


# --- timed-out wait ----------------------------------------------------------------------------


def test_timed_out_wait_can_be_expired():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _blocked_schedule(s, dep)
    far_future = datetime.now(timezone.utc) + timedelta(hours=2)

    check_result = s["timeout_service"].check("task-1", schedule.schedule_id, now=far_future)
    assert check_result.state == TIMED_OUT
    assert any("exceeded" in b for b in check_result.blockers)

    cancelled = s["timeout_service"].expire_wait("task-1", schedule.schedule_id, now=far_future)
    assert cancelled.status == "cancelled"
    assert cancelled.cancellation_reason.startswith("dependency wait timed out: ")


def test_expire_wait_raises_when_still_active():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _blocked_schedule(s, dep)

    with pytest.raises(InvalidAgentTaskRecoveryScheduleDependencyTimeoutError):
        s["timeout_service"].expire_wait("task-1", schedule.schedule_id)


# --- dependency resolution before timeout -------------------------------------------------------


def test_dependency_resolved_before_timeout_reports_not_waiting():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _blocked_schedule(s, dep)
    far_future = datetime.now(timezone.utc) + timedelta(hours=2)

    _advance_to(s["lifecycle_service"], dep, COMPLETED)
    result = s["timeout_service"].check("task-1", schedule.schedule_id, now=far_future)

    assert result.state == NOT_WAITING
    assert result.ready is True
    assert result.deadline is None

    with pytest.raises(InvalidAgentTaskRecoveryScheduleDependencyTimeoutError):
        s["timeout_service"].expire_wait("task-1", schedule.schedule_id, now=far_future)


# --- cancellation / completion -------------------------------------------------------------------


def test_cancelled_schedule_reports_not_applicable():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _blocked_schedule(s, dep)
    s["scheduling_service"].cancel("task-1", schedule.schedule_id, reason="no longer needed")

    result = s["timeout_service"].check("task-1", schedule.schedule_id)
    assert result.state == TIMEOUT_NOT_APPLICABLE
    assert result.ready is True

    # Idempotent no-op: expire_wait() on an already-cancelled schedule
    # never raises and never re-cancels.
    unchanged = s["timeout_service"].expire_wait("task-1", schedule.schedule_id)
    assert unchanged.status == "cancelled"
    assert unchanged.cancellation_reason == "no longer needed"


def test_completed_dependency_reports_not_applicable_style_not_waiting():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _blocked_schedule(s, dep)
    _advance_to(s["lifecycle_service"], dep, COMPLETED)

    result = s["timeout_service"].check("task-1", schedule.schedule_id)
    assert result.state == NOT_WAITING


def test_dispatched_schedule_reports_not_applicable():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    s["dependency_service"].add_dependency("task-1", dep.task_id)
    _fail_task(s["event_service"])
    _advance_to(s["lifecycle_service"], dep, COMPLETED)
    # No execute_at deferral this time -- due immediately, so dispatch()
    # itself succeeds (this test is about the ALREADY-dispatched state,
    # not about waiting).
    _, schedule = _scheduled(s)
    s["dispatch_service"].dispatch("task-1", schedule.schedule_id)

    result = s["timeout_service"].check("task-1", schedule.schedule_id)
    assert result.state == TIMEOUT_NOT_APPLICABLE
    assert "dispatched" in result.reason


def test_expired_schedule_reports_not_applicable():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    s["dependency_service"].add_dependency("task-1", dep.task_id)
    _fail_task(s["event_service"])
    _, schedule = _scheduled(s, execute_at=datetime.now(timezone.utc) - timedelta(hours=2))
    s["blocking_service"].block("task-1", schedule.schedule_id, (dep.task_id,), "waiting on dep")

    short_expiration_service = LLMAgentTaskRecoveryPreflightScheduleExpirationService(
        scheduling_service=s["scheduling_service"], max_overdue_age=timedelta(0)
    )
    timeout_service = LLMAgentTaskRecoveryPreflightScheduleDependencyTimeoutService(
        dependency_service=s["gate_service"], scheduling_service=s["scheduling_service"],
        blocking_service=s["blocking_service"], expiration_service=short_expiration_service,
    )

    result = timeout_service.check("task-1", schedule.schedule_id)
    assert result.state == TIMEOUT_NOT_APPLICABLE
    assert "already expired" in result.reason


# --- repeated timeout handling ---------------------------------------------------------------------


def test_repeated_expire_wait_is_idempotent():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _blocked_schedule(s, dep)
    far_future = datetime.now(timezone.utc) + timedelta(hours=2)

    first = s["timeout_service"].expire_wait("task-1", schedule.schedule_id, now=far_future)
    second = s["timeout_service"].expire_wait("task-1", schedule.schedule_id, now=far_future)

    assert first.status == second.status == "cancelled"
    assert first.cancellation_reason == second.cancellation_reason


# --- history preservation -----------------------------------------------------------------------------


def test_expire_wait_never_touches_dependency_or_blocking_history():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _blocked_schedule(s, dep)
    far_future = datetime.now(timezone.utc) + timedelta(hours=2)

    before_blocking_history = s["blocking_service"].get_history("task-1", schedule.schedule_id)
    s["timeout_service"].expire_wait("task-1", schedule.schedule_id, now=far_future)
    after_blocking_history = s["blocking_service"].get_history("task-1", schedule.schedule_id)

    assert before_blocking_history == after_blocking_history
    assert s["lifecycle_service"].get(dep.task_id).current_state == "created"


# --- dispatch remains blocked after timeout ---------------------------------------------------------


def test_dispatch_blocked_once_timed_out_even_before_expire_wait():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _blocked_schedule(s, dep)

    # validate() calls its own dependency_service.check() with no `now`
    # override (always the real wall clock) -- a zero-duration
    # max_wait_duration means the wait reads as TIMED_OUT the instant any
    # real time at all has passed since it started, so this proves
    # validate() blocks dispatch on its own, without expire_wait() ever
    # having been called.
    immediate_timeout_service = LLMAgentTaskRecoveryPreflightScheduleDependencyTimeoutService(
        dependency_service=s["gate_service"], scheduling_service=s["scheduling_service"],
        blocking_service=s["blocking_service"], expiration_service=s["expiration_service"],
        max_wait_duration=timedelta(0),
    )
    assert immediate_timeout_service.check("task-1", schedule.schedule_id).state == TIMED_OUT

    wired_validation_service = LLMAgentTaskRecoveryPreflightScheduleValidationService(
        scheduling_service=s["scheduling_service"],
        authorization_validation_service=s["authorization_validation_service"],
        dependency_service=immediate_timeout_service,
    )
    validation = wired_validation_service.validate("task-1", schedule.schedule_id)
    assert validation.valid is False
    assert any("exceeded" in reason for reason in validation.blocking_reasons)


def test_dispatch_remains_blocked_after_expire_wait():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _blocked_schedule(s, dep)
    far_future = datetime.now(timezone.utc) + timedelta(hours=2)

    s["timeout_service"].expire_wait("task-1", schedule.schedule_id, now=far_future)

    validation = s["timeout_wired_validation_service"].validate("task-1", schedule.schedule_id)
    assert validation.valid is False
    with pytest.raises(InvalidAgentTaskRecoveryScheduleDispatchError):
        s["timeout_wired_dispatch_service"].dispatch("task-1", schedule.schedule_id)


# --- argument validation ------------------------------------------------------------------------------


def test_check_rejects_blank_arguments_and_unknown_schedule():
    s = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryScheduleDependencyTimeoutError):
        s["timeout_service"].check("", "id")
    with pytest.raises(InvalidAgentTaskRecoveryScheduleDependencyTimeoutError):
        s["timeout_service"].check("task-1", "")
    with pytest.raises(InvalidAgentTaskRecoveryScheduleDependencyTimeoutError):
        s["timeout_service"].check("task-1", "never-existed")
