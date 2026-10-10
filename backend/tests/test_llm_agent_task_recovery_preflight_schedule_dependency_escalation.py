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
from backend.agent_task_queue import LLMAgentTaskQueueService
from backend.agent_task_queue_dead_letter import LLMAgentTaskDeadLetterService
from backend.agent_task_queue_retry_eligibility import LLMAgentTaskQueueRetryEligibilityService
from backend.agent_task_queue_retry_scheduler import LLMAgentTaskRetryScheduler
from backend.agent_task_readiness import (
    AgentTaskReadinessCheck,
    AgentTaskReadinessResult,
    LLMAgentTaskReadinessService,
)
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
    DEPENDENCY_WAIT_ESCALATED_EVENT_TYPE,
    NOT_WAITING,
    TIMED_OUT,
    TIMEOUT_ACTIVE,
    TIMEOUT_NOT_APPLICABLE,
    InvalidAgentTaskRecoveryScheduleDependencyEscalationError,
    LLMAgentTaskRecoveryPreflightScheduleDependencyBlockingService,
    LLMAgentTaskRecoveryPreflightScheduleDependencyEscalationService,
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


class _FakeRetryEligibilityServiceForGuard:
    def check(self, task_id):
        from backend.agent_task_queue_retry_eligibility import RetryEligibilityResult

        return RetryEligibilityResult(task_id=task_id, eligible=True, reason="eligible")


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


def _queue_lifecycle_stack():
    lifecycle_service = LLMAgentTaskLifecycleService()
    readiness_service = LLMAgentTaskReadinessService(lifecycle_service)
    queue_service = LLMAgentTaskQueueService(readiness_service)
    dead_letter_service = LLMAgentTaskDeadLetterService(queue_service, lifecycle_service)
    eligibility_service = LLMAgentTaskQueueRetryEligibilityService(
        lifecycle_service, readiness_service, dead_letter_service
    )
    retry_scheduler = LLMAgentTaskRetryScheduler(eligibility_service)
    return lifecycle_service, retry_scheduler


def _stack(**definition_overrides):
    lifecycle_service, retry_scheduler = _queue_lifecycle_stack()
    task = _task(lifecycle_service, task_id="task-1", **definition_overrides)
    task = lifecycle_service.transition(task.task_id, PLANNED)
    task = lifecycle_service.transition(task.task_id, READY)

    dependency_service = LLMAgentTaskDependencyService(lifecycle_service)
    dependency_resolver = LLMAgentTaskDependencyResolver(lifecycle_service, dependency_service)

    store = InMemoryAgentTaskEventStore()
    event_service = LLMAgentTaskEventService(store=store)
    query_service = LLMAgentTaskEventQueryService(store=store)
    classifier = LLMAgentTaskEventFailureClassifier(query_service=query_service)
    replay_service = LLMAgentTaskEventReplayService(query_service=query_service)

    readiness = _FakeReadinessService()
    retry_eligibility_fake = _FakeRetryEligibilityServiceForGuard()

    planner = LLMAgentTaskEventFailureRecoveryPlanner(
        classifier=classifier, readiness_service=readiness, retry_eligibility_service=retry_eligibility_fake
    )
    guard = LLMAgentTaskRecoveryGuardService(
        classifier=classifier, replay_service=replay_service,
        readiness_service=readiness, retry_eligibility_service=retry_eligibility_fake,
        retry_scheduler=_FakeRetryScheduler(), dead_letter_service=_FakeDeadLetterService(),
        reservation_service=_FakeReservationService(),
    )
    evaluation_service = LLMAgentTaskRecoveryGuardEvaluationService(guard_service=guard)
    preflight_service = LLMAgentTaskRecoveryPreflightService(planner=planner, evaluation_service=evaluation_service)
    preflight_store = LLMAgentTaskRecoveryPreflightStore()
    freshness_service = LLMAgentTaskRecoveryPreflightFreshnessService(
        preflight_store=preflight_store, classifier=classifier, replay_service=replay_service,
        readiness_service=readiness, retry_eligibility_service=retry_eligibility_fake,
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
    escalation_service = LLMAgentTaskRecoveryPreflightScheduleDependencyEscalationService(
        timeout_service=timeout_service, scheduling_service=scheduling_service,
        retry_scheduler=retry_scheduler, preflight_store=preflight_store, event_service=event_service,
    )
    timeout_wired_validation_service = LLMAgentTaskRecoveryPreflightScheduleValidationService(
        scheduling_service=scheduling_service, authorization_validation_service=authorization_validation_service,
        dependency_service=timeout_service,
    )
    timeout_wired_dispatch_service = LLMAgentTaskRecoveryPreflightScheduleDispatchService(
        validation_service=timeout_wired_validation_service, scheduling_service=scheduling_service,
    )

    return {
        "event_service": event_service,
        "query_service": query_service,
        "preflight_service": preflight_service,
        "preflight_store": preflight_store,
        "approval_service": approval_service,
        "scheduling_service": scheduling_service,
        "lifecycle_service": lifecycle_service,
        "dependency_service": dependency_service,
        "gate_service": gate_service,
        "blocking_service": blocking_service,
        "timeout_service": timeout_service,
        "escalation_service": escalation_service,
        "retry_scheduler": retry_scheduler,
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


# --- normal wait -----------------------------------------------------------------------------


def test_normal_wait_should_not_escalate():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _blocked_schedule(s, dep)

    result = s["escalation_service"].assess("task-1", schedule.schedule_id)

    assert result.timeout_state == TIMEOUT_ACTIVE
    assert result.should_escalate is False
    with pytest.raises(InvalidAgentTaskRecoveryScheduleDependencyEscalationError):
        s["escalation_service"].escalate("task-1", schedule.schedule_id)


# --- threshold reached -------------------------------------------------------------------------


def test_threshold_reached_can_escalate():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _blocked_schedule(s, dep)
    far_future = datetime.now(timezone.utc) + timedelta(hours=2)

    assessment = s["escalation_service"].assess("task-1", schedule.schedule_id, now=far_future)
    assert assessment.timeout_state == TIMED_OUT
    assert assessment.should_escalate is True
    assert assessment.dependency_evidence != ()

    result = s["escalation_service"].escalate("task-1", schedule.schedule_id, now=far_future)
    assert result.already_escalated is True
    assert result.should_escalate is False


# --- insufficient evidence ----------------------------------------------------------------------


def test_insufficient_evidence_cannot_escalate():
    s = _stack()
    _fail_task(s["event_service"])
    _, schedule = _scheduled(s)

    result = s["escalation_service"].assess("task-1", schedule.schedule_id)
    assert result.timeout_state == NOT_WAITING
    assert result.should_escalate is False

    with pytest.raises(InvalidAgentTaskRecoveryScheduleDependencyEscalationError):
        s["escalation_service"].escalate("task-1", schedule.schedule_id)


# --- already-escalated schedules / idempotency --------------------------------------------------


def test_repeated_escalate_is_idempotent():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _blocked_schedule(s, dep)
    far_future = datetime.now(timezone.utc) + timedelta(hours=2)

    first = s["escalation_service"].escalate("task-1", schedule.schedule_id, now=far_future)
    second = s["escalation_service"].escalate("task-1", schedule.schedule_id, now=far_future)

    assert first.already_escalated is True
    assert second.already_escalated is True
    history = s["escalation_service"].get_history("task-1", schedule.schedule_id)
    assert len(history) == 1


# --- resolved dependencies ----------------------------------------------------------------------


def test_resolved_dependency_after_escalation_does_not_unescalate():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _blocked_schedule(s, dep)
    far_future = datetime.now(timezone.utc) + timedelta(hours=2)
    s["escalation_service"].escalate("task-1", schedule.schedule_id, now=far_future)

    _advance_to(s["lifecycle_service"], dep, COMPLETED)
    result = s["escalation_service"].assess("task-1", schedule.schedule_id, now=far_future)

    assert result.timeout_state == NOT_WAITING
    assert result.already_escalated is True
    assert result.should_escalate is False
    assert len(s["escalation_service"].get_history("task-1", schedule.schedule_id)) == 1


# --- expired / cancelled schedules ----------------------------------------------------------------


def test_cancelled_schedule_cannot_escalate():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _blocked_schedule(s, dep)
    s["scheduling_service"].cancel("task-1", schedule.schedule_id, reason="no longer needed")

    result = s["escalation_service"].assess("task-1", schedule.schedule_id)
    assert result.timeout_state == TIMEOUT_NOT_APPLICABLE
    assert result.should_escalate is False
    with pytest.raises(InvalidAgentTaskRecoveryScheduleDependencyEscalationError):
        s["escalation_service"].escalate("task-1", schedule.schedule_id)


def test_expired_schedule_cannot_escalate():
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
    escalation_service = LLMAgentTaskRecoveryPreflightScheduleDependencyEscalationService(
        timeout_service=timeout_service, scheduling_service=s["scheduling_service"],
    )

    result = escalation_service.assess("task-1", schedule.schedule_id)
    assert result.timeout_state == TIMEOUT_NOT_APPLICABLE
    with pytest.raises(InvalidAgentTaskRecoveryScheduleDependencyEscalationError):
        escalation_service.escalate("task-1", schedule.schedule_id)


# --- history preservation -----------------------------------------------------------------------


def test_escalation_never_touches_other_histories():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _blocked_schedule(s, dep)
    far_future = datetime.now(timezone.utc) + timedelta(hours=2)

    before_blocking_history = s["blocking_service"].get_history("task-1", schedule.schedule_id)
    before_schedule = s["scheduling_service"].get("task-1", schedule.schedule_id)

    s["escalation_service"].escalate("task-1", schedule.schedule_id, now=far_future)

    after_blocking_history = s["blocking_service"].get_history("task-1", schedule.schedule_id)
    after_schedule = s["scheduling_service"].get("task-1", schedule.schedule_id)

    assert before_blocking_history == after_blocking_history
    assert before_schedule == after_schedule
    assert s["lifecycle_service"].get(dep.task_id).current_state == "created"


def test_escalation_history_is_ordered_and_immutable():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _blocked_schedule(s, dep)
    far_future = datetime.now(timezone.utc) + timedelta(hours=2)

    escalated = s["escalation_service"].escalate("task-1", schedule.schedule_id, now=far_future)
    history = s["escalation_service"].get_history("task-1", schedule.schedule_id)

    assert len(history) == 1
    assert history[0].task_id == "task-1"
    assert history[0].schedule_id == schedule.schedule_id
    assert history[0].dependency_evidence == escalated.dependency_evidence


# --- escalation cannot bypass execution gates ----------------------------------------------------


def test_escalation_cannot_bypass_execution_gates():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _blocked_schedule(s, dep)
    far_future = datetime.now(timezone.utc) + timedelta(hours=2)

    before = s["timeout_wired_validation_service"].validate("task-1", schedule.schedule_id)
    assert before.valid is False
    with pytest.raises(InvalidAgentTaskRecoveryScheduleDispatchError):
        s["timeout_wired_dispatch_service"].dispatch("task-1", schedule.schedule_id)

    s["escalation_service"].escalate("task-1", schedule.schedule_id, now=far_future)

    after = s["timeout_wired_validation_service"].validate("task-1", schedule.schedule_id)
    assert after.valid is False
    assert after.blocking_reasons == before.blocking_reasons
    with pytest.raises(InvalidAgentTaskRecoveryScheduleDispatchError):
        s["timeout_wired_dispatch_service"].dispatch("task-1", schedule.schedule_id)

    # The schedule itself is completely untouched by escalation.
    assert s["scheduling_service"].get("task-1", schedule.schedule_id).status == "scheduled"


# --- existing event mechanism --------------------------------------------------------------------


def test_escalate_emits_existing_event_mechanism():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _blocked_schedule(s, dep)
    far_future = datetime.now(timezone.utc) + timedelta(hours=2)

    s["escalation_service"].escalate("task-1", schedule.schedule_id, now=far_future)

    events = s["query_service"].query(task_id="task-1", event_types=(DEPENDENCY_WAIT_ESCALATED_EVENT_TYPE,))
    assert len(events) == 1
    assert events[0].payload.get("schedule_id") == schedule.schedule_id


def test_escalate_works_without_event_service():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _blocked_schedule(s, dep)
    far_future = datetime.now(timezone.utc) + timedelta(hours=2)

    escalation_service = LLMAgentTaskRecoveryPreflightScheduleDependencyEscalationService(
        timeout_service=s["timeout_service"], scheduling_service=s["scheduling_service"],
    )

    result = escalation_service.escalate("task-1", schedule.schedule_id, now=far_future)
    assert result.already_escalated is True


# --- attempts / policy context (where available) --------------------------------------------------


def test_assess_includes_attempts_and_policy_context_when_available():
    s = _stack(attempt_count=1, max_attempts=5)
    dep = _task(s["lifecycle_service"])
    schedule = _blocked_schedule(s, dep)
    far_future = datetime.now(timezone.utc) + timedelta(hours=2)

    result = s["escalation_service"].assess("task-1", schedule.schedule_id, now=far_future)

    # resolve_eligibility()'s own attempt_count is the raw recorded
    # value (unlike Commit #7-of-agent_task_recovery_scheduling's own
    # backoff.calculate(), which reports attempt_count + 1 for "the
    # attempt about to be made" -- this service reuses resolve_eligibility()
    # directly, never that +1 convention).
    assert result.attempt_count == 1
    assert result.remaining_attempts == 4
    assert result.policy_decision is not None


# --- argument validation ---------------------------------------------------------------------------


def test_assess_rejects_blank_arguments_and_unknown_schedule():
    s = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryScheduleDependencyEscalationError):
        s["escalation_service"].assess("", "id")
    with pytest.raises(InvalidAgentTaskRecoveryScheduleDependencyEscalationError):
        s["escalation_service"].assess("task-1", "")
    with pytest.raises(InvalidAgentTaskRecoveryScheduleDependencyEscalationError):
        s["escalation_service"].assess("task-1", "never-existed")
