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
    RESOLUTION_TERMINAL,
    RESOLUTION_WOKEN,
    InMemoryAgentTaskRecoveryScheduleEscalationStore,
    InvalidAgentTaskRecoveryScheduleEscalationResolutionError,
    LLMAgentTaskRecoveryPreflightScheduleDependencyBlockingService,
    LLMAgentTaskRecoveryPreflightScheduleDependencyEscalationResolutionService,
    LLMAgentTaskRecoveryPreflightScheduleDependencyEscalationService,
    LLMAgentTaskRecoveryPreflightScheduleDependencyReconciliationService,
    LLMAgentTaskRecoveryPreflightScheduleDependencyService,
    LLMAgentTaskRecoveryPreflightScheduleDependencyTimeoutService,
    LLMAgentTaskRecoveryPreflightScheduleDependencyWakeService,
)
from backend.agent_task_recovery_scheduling import (
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
    timeout_service = LLMAgentTaskRecoveryPreflightScheduleDependencyTimeoutService(
        dependency_service=gate_service, scheduling_service=scheduling_service,
        blocking_service=blocking_service, expiration_service=expiration_service,
        dispatch_service=dispatch_service, max_wait_duration=timedelta(hours=1),
    )
    escalation_store = InMemoryAgentTaskRecoveryScheduleEscalationStore()
    escalation_service = LLMAgentTaskRecoveryPreflightScheduleDependencyEscalationService(
        timeout_service=timeout_service, scheduling_service=scheduling_service, preflight_store=preflight_store,
        store=escalation_store,
    )
    wake_service = LLMAgentTaskRecoveryPreflightScheduleDependencyWakeService(
        reconciliation_service=reconciliation_service, scheduling_service=scheduling_service,
        validation_service=plain_validation_service, expiration_service=expiration_service,
        blocking_service=blocking_service,
    )
    resolution_service = LLMAgentTaskRecoveryPreflightScheduleDependencyEscalationResolutionService(
        escalation_service=escalation_service, wake_service=wake_service,
        reconciliation_service=reconciliation_service, scheduling_service=scheduling_service,
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
        "authorization_service": authorization_service,
        "scheduling_service": scheduling_service,
        "lifecycle_service": lifecycle_service,
        "dependency_service": dependency_service,
        "gate_service": gate_service,
        "reconciliation_service": reconciliation_service,
        "blocking_service": blocking_service,
        "expiration_service": expiration_service,
        "validation_service": plain_validation_service,
        "dispatch_service": dispatch_service,
        "timeout_service": timeout_service,
        "escalation_service": escalation_service,
        "escalation_store": escalation_store,
        "wake_service": wake_service,
        "resolution_service": resolution_service,
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


def _escalated_schedule(s, dep, task_id="task-1"):
    s["dependency_service"].add_dependency(task_id, dep.task_id)
    _fail_task(s["event_service"], task_id)
    # execute_at is deferred well beyond far_future below, so "already
    # awake" (execute_at <= now) never accidentally triggers once wake()
    # is asked to act at far_future -- and far_future itself is well
    # past the 1h Commit #6 timeout threshold, so escalate() succeeds.
    _, schedule = _scheduled(s, task_id=task_id, execute_at=datetime.now(timezone.utc) + timedelta(hours=6))
    s["blocking_service"].block(task_id, schedule.schedule_id, (dep.task_id,), "waiting on dep")
    far_future = datetime.now(timezone.utc) + timedelta(hours=2)
    s["escalation_service"].escalate(task_id, schedule.schedule_id, now=far_future)
    return schedule, far_future


# --- dependency resolved / successful return to validation ---------------------------------------


def test_dependency_resolved_returns_schedule_to_validation_path():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule, far_future = _escalated_schedule(s, dep)

    _advance_to(s["lifecycle_service"], dep, COMPLETED)
    check_result = s["resolution_service"].check("task-1", schedule.schedule_id, now=far_future)
    assert check_result.can_resolve is True
    assert check_result.outcome == RESOLUTION_WOKEN

    resolved = s["resolution_service"].resolve("task-1", schedule.schedule_id, now=far_future)
    assert resolved.already_resolved is True
    assert resolved.outcome == RESOLUTION_WOKEN

    records = s["scheduling_service"].list("task-1")
    new_record = next(r for r in records if r.status == SCHEDULED)
    assert new_record.schedule_id != schedule.schedule_id
    assert new_record.execute_at is None

    validation = s["validation_service"].validate("task-1", new_record.schedule_id)
    assert validation.valid is True


# --- dependency still blocked ---------------------------------------------------------------------


def test_dependency_still_blocked_preserves_escalation():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule, far_future = _escalated_schedule(s, dep)

    check_result = s["resolution_service"].check("task-1", schedule.schedule_id, now=far_future)
    assert check_result.can_resolve is False
    assert check_result.outcome is None

    resolved = s["resolution_service"].resolve("task-1", schedule.schedule_id, now=far_future)
    assert resolved.already_resolved is False
    assert resolved.can_resolve is False

    assert s["resolution_service"].get_history("task-1", schedule.schedule_id) == []
    assert len(s["escalation_service"].get_history("task-1", schedule.schedule_id)) == 1
    # The original schedule is completely untouched.
    assert s["scheduling_service"].get("task-1", schedule.schedule_id).status == "scheduled"


# --- schedule expired/cancelled while escalated -----------------------------------------------------


def test_cancelled_schedule_resolves_into_terminal_state():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule, far_future = _escalated_schedule(s, dep)
    s["scheduling_service"].cancel("task-1", schedule.schedule_id, reason="no longer needed")

    result = s["resolution_service"].resolve("task-1", schedule.schedule_id, now=far_future)

    assert result.already_resolved is True
    assert result.outcome == RESOLUTION_TERMINAL
    # No new schedule was created -- resolve() never tries to "make it actionable".
    records = s["scheduling_service"].list("task-1")
    assert len(records) == 1
    assert records[0].status == "cancelled"


def test_expired_schedule_resolves_into_terminal_state():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    s["dependency_service"].add_dependency("task-1", dep.task_id)
    _fail_task(s["event_service"])
    # Already due (execute_at in the past), but the main stack's own
    # expiration_service uses the long 24h default TTL, so escalate()
    # below still succeeds on the dependency-wait threshold alone,
    # never on general schedule expiration.
    _, schedule = _scheduled(s, execute_at=datetime.now(timezone.utc) - timedelta(minutes=10))
    s["blocking_service"].block("task-1", schedule.schedule_id, (dep.task_id,), "waiting on dep")
    past_wait_threshold = datetime.now(timezone.utc) + timedelta(hours=2)
    s["escalation_service"].escalate("task-1", schedule.schedule_id, now=past_wait_threshold)

    # Simulate time passing far enough that Commit #9's own general
    # schedule-expiration mechanism would ALSO now consider this
    # schedule expired -- a resolution stack wired with a much shorter
    # expiration window than the main stack's, but sharing the SAME
    # escalation store, so it sees this exact escalation as already
    # recorded.
    short_expiration_service = LLMAgentTaskRecoveryPreflightScheduleExpirationService(
        scheduling_service=s["scheduling_service"], max_overdue_age=timedelta(0)
    )
    timeout_service = LLMAgentTaskRecoveryPreflightScheduleDependencyTimeoutService(
        dependency_service=s["gate_service"], scheduling_service=s["scheduling_service"],
        blocking_service=s["blocking_service"], expiration_service=short_expiration_service,
    )
    escalation_service = LLMAgentTaskRecoveryPreflightScheduleDependencyEscalationService(
        timeout_service=timeout_service, scheduling_service=s["scheduling_service"], store=s["escalation_store"],
    )
    resolution_service = LLMAgentTaskRecoveryPreflightScheduleDependencyEscalationResolutionService(
        escalation_service=escalation_service, wake_service=s["wake_service"],
        reconciliation_service=s["reconciliation_service"], scheduling_service=s["scheduling_service"],
    )

    result = resolution_service.resolve("task-1", schedule.schedule_id, now=past_wait_threshold)

    assert result.outcome == RESOLUTION_TERMINAL
    records = s["scheduling_service"].list("task-1")
    assert len(records) == 1  # no new schedule created


# --- stale preflight -----------------------------------------------------------------------------


def test_revoked_authorization_resolves_into_terminal_state():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule, far_future = _escalated_schedule(s, dep)
    s["authorization_service"].revoke("task-1", schedule.authorization_id, reason="revoked externally")

    result = s["resolution_service"].resolve("task-1", schedule.schedule_id, now=far_future)

    assert result.outcome == RESOLUTION_TERMINAL
    records = s["scheduling_service"].list("task-1")
    assert len(records) == 1  # no new schedule created


# --- repeated resolution is idempotent --------------------------------------------------------------


def test_repeated_resolution_is_idempotent():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule, far_future = _escalated_schedule(s, dep)
    _advance_to(s["lifecycle_service"], dep, COMPLETED)

    first = s["resolution_service"].resolve("task-1", schedule.schedule_id, now=far_future)
    second = s["resolution_service"].resolve("task-1", schedule.schedule_id, now=far_future)

    assert first.outcome == second.outcome == RESOLUTION_WOKEN
    history = s["resolution_service"].get_history("task-1", schedule.schedule_id)
    assert len(history) == 1
    records = s["scheduling_service"].list("task-1")
    assert sum(1 for r in records if r.status == SCHEDULED) == 1


def test_resolve_raises_when_never_escalated():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    s["dependency_service"].add_dependency("task-1", dep.task_id)
    _fail_task(s["event_service"])
    _, schedule = _scheduled(s, execute_at=datetime.now(timezone.utc) + timedelta(hours=2))

    with pytest.raises(InvalidAgentTaskRecoveryScheduleEscalationResolutionError):
        s["resolution_service"].resolve("task-1", schedule.schedule_id)


# --- history preservation -----------------------------------------------------------------------------


def test_resolution_preserves_escalation_and_dependency_history():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule, far_future = _escalated_schedule(s, dep)
    escalation_history_before = s["escalation_service"].get_history("task-1", schedule.schedule_id)
    blocking_history_before = s["blocking_service"].get_history("task-1", schedule.schedule_id)

    _advance_to(s["lifecycle_service"], dep, COMPLETED)
    s["resolution_service"].resolve("task-1", schedule.schedule_id, now=far_future)

    assert s["escalation_service"].get_history("task-1", schedule.schedule_id) == escalation_history_before
    assert s["blocking_service"].get_history("task-1", schedule.schedule_id) == blocking_history_before

    resolution_history = s["resolution_service"].get_history("task-1", schedule.schedule_id)
    assert len(resolution_history) == 1
    assert resolution_history[0].outcome == RESOLUTION_WOKEN


# --- resolution never directly executes recovery ------------------------------------------------------


def test_resolution_never_directly_dispatches():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule, far_future = _escalated_schedule(s, dep)
    _advance_to(s["lifecycle_service"], dep, COMPLETED)

    s["resolution_service"].resolve("task-1", schedule.schedule_id, now=far_future)

    # resolve() itself never calls dispatch() -- nothing has been dispatched yet.
    assert s["dispatch_service"].list("task-1") == []

    new_record = next(r for r in s["scheduling_service"].list("task-1") if r.status == SCHEDULED)
    dispatched = s["dispatch_service"].dispatch("task-1", new_record.schedule_id)
    assert dispatched.status == "dispatched"


# --- argument validation ---------------------------------------------------------------------------


def test_check_rejects_blank_arguments_and_unknown_schedule():
    s = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryScheduleEscalationResolutionError):
        s["resolution_service"].check("", "id")
    with pytest.raises(InvalidAgentTaskRecoveryScheduleEscalationResolutionError):
        s["resolution_service"].check("task-1", "")
    with pytest.raises(InvalidAgentTaskRecoveryScheduleEscalationResolutionError):
        s["resolution_service"].check("task-1", "never-existed")
