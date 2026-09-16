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
    AgentTaskRecoveryScheduleDependencyWaitPlan,
    InvalidAgentTaskRecoveryScheduleDependencyWaitError,
    LLMAgentTaskRecoveryPreflightScheduleDependencyService,
    LLMAgentTaskRecoveryPreflightScheduleDependencyWaitService,
)
from backend.agent_task_recovery_scheduling import (
    CANCELLED,
    SCHEDULED,
    InvalidAgentTaskRecoveryScheduleDispatchError,
    LLMAgentTaskRecoveryPreflightScheduleBackoffService,
    LLMAgentTaskRecoveryPreflightScheduleDispatchService,
    LLMAgentTaskRecoveryPreflightScheduleExpirationService,
    LLMAgentTaskRecoveryPreflightSchedulingService,
    LLMAgentTaskRecoveryPreflightScheduleValidationService,
)

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


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


def _fail_task(event_service, task_id="task-1"):
    event_service.emit(task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})
    return event_service.emit(task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": FAILED})


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
    gate_service = LLMAgentTaskRecoveryPreflightScheduleDependencyService(
        scheduling_service=scheduling_service, dependency_resolver=dependency_resolver
    )

    plain_validation_service = LLMAgentTaskRecoveryPreflightScheduleValidationService(
        scheduling_service=scheduling_service, authorization_validation_service=authorization_validation_service,
    )
    expiration_service = LLMAgentTaskRecoveryPreflightScheduleExpirationService(scheduling_service=scheduling_service)
    backoff_service = LLMAgentTaskRecoveryPreflightScheduleBackoffService(
        retry_scheduler=retry_scheduler, scheduling_service=scheduling_service
    )
    wait_service = LLMAgentTaskRecoveryPreflightScheduleDependencyWaitService(
        dependency_service=gate_service, scheduling_service=scheduling_service,
        validation_service=plain_validation_service, expiration_service=expiration_service,
        backoff_service=backoff_service,
    )
    dispatch_service = LLMAgentTaskRecoveryPreflightScheduleDispatchService(
        validation_service=plain_validation_service, scheduling_service=scheduling_service,
    )

    return {
        "task": task,
        "event_service": event_service,
        "preflight_service": preflight_service,
        "preflight_store": preflight_store,
        "approval_service": approval_service,
        "scheduling_service": scheduling_service,
        "lifecycle_service": lifecycle_service,
        "dependency_service": dependency_service,
        "gate_service": gate_service,
        "retry_scheduler": retry_scheduler,
        "backoff_service": backoff_service,
        "expiration_service": expiration_service,
        "validation_service": plain_validation_service,
        "wait_service": wait_service,
        "dispatch_service": dispatch_service,
    }


def _scheduled(s, task_id="task-1", execute_at=None):
    _fail_task(s["event_service"], task_id)
    preflight = s["preflight_store"].save(s["preflight_service"].run(task_id))
    s["approval_service"].request(task_id, preflight.preflight_id)
    s["approval_service"].approve(task_id, preflight.preflight_id, actor="alice")
    schedule = s["scheduling_service"].schedule(task_id, preflight.preflight_id, execute_at=execute_at)
    return preflight, schedule


# --- blocked dependency -> wait plan -----------------------------------------------------


def test_plan_wait_created_when_dependency_blocked():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    s["dependency_service"].add_dependency("task-1", dep.task_id)
    _, schedule = _scheduled(s)

    plan = s["wait_service"].plan_wait("task-1", schedule.schedule_id, now=NOW)

    assert isinstance(plan, AgentTaskRecoveryScheduleDependencyWaitPlan)
    assert plan.preflight_id == schedule.preflight_id
    assert plan.next_check_at > NOW
    assert plan.dependency_evidence != ()


def test_plan_wait_rejected_when_dependencies_already_ready():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    s["dependency_service"].add_dependency("task-1", dep.task_id)
    _advance_to(s["lifecycle_service"], dep, COMPLETED)
    _, schedule = _scheduled(s)

    with pytest.raises(InvalidAgentTaskRecoveryScheduleDependencyWaitError):
        s["wait_service"].plan_wait("task-1", schedule.schedule_id, now=NOW)


# --- deadline / expiration limits ---------------------------------------------------------


def test_plan_wait_rejects_expired_schedule():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    s["dependency_service"].add_dependency("task-1", dep.task_id)
    _, schedule = _scheduled(s, execute_at=NOW - timedelta(hours=2))
    short_expiration_service = LLMAgentTaskRecoveryPreflightScheduleExpirationService(
        scheduling_service=s["scheduling_service"], max_overdue_age=timedelta(0)
    )
    wait_service = LLMAgentTaskRecoveryPreflightScheduleDependencyWaitService(
        dependency_service=s["gate_service"], scheduling_service=s["scheduling_service"],
        validation_service=s["validation_service"], expiration_service=short_expiration_service,
    )

    with pytest.raises(InvalidAgentTaskRecoveryScheduleDependencyWaitError, match="expiration window"):
        wait_service.plan_wait("task-1", schedule.schedule_id, now=NOW)


def test_plan_wait_caps_next_check_at_to_expiration_deadline():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    s["dependency_service"].add_dependency("task-1", dep.task_id)
    _, schedule = _scheduled(s, execute_at=NOW - timedelta(minutes=10))
    capped_expiration_service = LLMAgentTaskRecoveryPreflightScheduleExpirationService(
        scheduling_service=s["scheduling_service"], max_overdue_age=timedelta(minutes=30)
    )
    wait_service = LLMAgentTaskRecoveryPreflightScheduleDependencyWaitService(
        dependency_service=s["gate_service"], scheduling_service=s["scheduling_service"],
        validation_service=s["validation_service"],
        expiration_service=capped_expiration_service, default_wait_interval=timedelta(hours=2),
    )

    plan = wait_service.plan_wait("task-1", schedule.schedule_id, now=NOW)

    # default_wait_interval alone would push next_check_at to NOW+2h, well
    # past the schedule's own expiration deadline (execute_at - 10min +
    # 30min TTL = NOW + 20min) -- capped instead.
    assert plan.next_check_at == NOW + timedelta(minutes=20)


# --- cancellation ---------------------------------------------------------------------------


def test_plan_wait_rejects_cancelled_schedule():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    s["dependency_service"].add_dependency("task-1", dep.task_id)
    _, schedule = _scheduled(s)
    s["scheduling_service"].cancel("task-1", schedule.schedule_id, reason="no longer needed")

    with pytest.raises(InvalidAgentTaskRecoveryScheduleDependencyWaitError):
        s["wait_service"].plan_wait("task-1", schedule.schedule_id, now=NOW)


# --- retry-count preservation / policy limits ------------------------------------------------


def test_planning_and_applying_wait_never_changes_retry_attempt_count():
    s = _stack(attempt_count=2, max_attempts=5)
    dep = _task(s["lifecycle_service"])
    s["dependency_service"].add_dependency("task-1", dep.task_id)
    _, schedule = _scheduled(s)

    before = s["retry_scheduler"].resolve_eligibility("task-1", now=NOW)
    plan = s["wait_service"].plan_wait("task-1", schedule.schedule_id, now=NOW)
    s["wait_service"].apply_wait("task-1", schedule.schedule_id, plan, now=NOW)
    after = s["retry_scheduler"].resolve_eligibility("task-1", now=NOW)

    assert before.attempt_count == after.attempt_count
    assert before.remaining_attempts == after.remaining_attempts


def test_plan_wait_rejects_when_retry_attempts_exhausted():
    s = _stack(attempt_count=3, max_attempts=3)
    dep = _task(s["lifecycle_service"])
    s["dependency_service"].add_dependency("task-1", dep.task_id)
    _, schedule = _scheduled(s)

    with pytest.raises(InvalidAgentTaskRecoveryScheduleDependencyWaitError):
        s["wait_service"].plan_wait("task-1", schedule.schedule_id, now=NOW)


# --- dependency becoming ready ------------------------------------------------------------


def test_apply_wait_leaves_schedule_untouched_once_dependency_becomes_ready():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    s["dependency_service"].add_dependency("task-1", dep.task_id)
    _, schedule = _scheduled(s)
    plan = s["wait_service"].plan_wait("task-1", schedule.schedule_id, now=NOW)

    _advance_to(s["lifecycle_service"], dep, COMPLETED)
    result = s["wait_service"].apply_wait("task-1", schedule.schedule_id, plan, now=NOW)

    assert result.schedule_id == schedule.schedule_id
    assert result.status == SCHEDULED
    assert result.execute_at == schedule.execute_at

    validation = s["validation_service"].validate("task-1", schedule.schedule_id)
    assert validation.valid is True


# --- repeated application is idempotent ------------------------------------------------------


def test_repeated_apply_wait_is_idempotent():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    s["dependency_service"].add_dependency("task-1", dep.task_id)
    _, schedule = _scheduled(s)
    plan = s["wait_service"].plan_wait("task-1", schedule.schedule_id, now=NOW)

    first = s["wait_service"].apply_wait("task-1", schedule.schedule_id, plan, now=NOW)
    second = s["wait_service"].apply_wait("task-1", schedule.schedule_id, plan, now=NOW)

    assert first.schedule_id == second.schedule_id
    assert first.execute_at == second.execute_at
    records = s["scheduling_service"].list("task-1")
    assert len(records) == 2  # the original (now cancelled) + exactly one new schedule
    assert sum(1 for r in records if r.status == SCHEDULED) == 1


# --- history preservation -----------------------------------------------------------------


def test_history_preserved_across_wait_application():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    s["dependency_service"].add_dependency("task-1", dep.task_id)
    _, schedule = _scheduled(s)
    plan = s["wait_service"].plan_wait("task-1", schedule.schedule_id, now=NOW)

    new_schedule = s["wait_service"].apply_wait("task-1", schedule.schedule_id, plan, now=NOW)

    records = {r.schedule_id: r for r in s["scheduling_service"].list("task-1")}
    assert schedule.schedule_id in records
    assert records[schedule.schedule_id].status == CANCELLED
    assert records[schedule.schedule_id].preflight_id == schedule.preflight_id
    assert new_schedule.schedule_id in records
    assert records[new_schedule.schedule_id].status == SCHEDULED
    assert records[new_schedule.schedule_id].execute_at == plan.next_check_at


# --- waiting never executes recovery -------------------------------------------------------


def test_waiting_never_executes_recovery():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    s["dependency_service"].add_dependency("task-1", dep.task_id)
    _, schedule = _scheduled(s)
    # validate()'s own execution-window check reads the real wall clock
    # (it takes no `now` override), so the plan must be computed relative
    # to real "now" for the resulting execute_at to genuinely still be in
    # the future when dispatch() is attempted below.
    real_now = datetime.now(timezone.utc)
    plan = s["wait_service"].plan_wait("task-1", schedule.schedule_id, now=real_now)

    new_schedule = s["wait_service"].apply_wait("task-1", schedule.schedule_id, plan, now=real_now)

    assert new_schedule.status == SCHEDULED
    with pytest.raises(InvalidAgentTaskRecoveryScheduleDispatchError):
        s["dispatch_service"].dispatch("task-1", new_schedule.schedule_id)
    assert s["dispatch_service"].list("task-1") == []


# --- argument validation -----------------------------------------------------------------


def test_plan_wait_rejects_blank_arguments_and_unknown_schedule():
    s = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryScheduleDependencyWaitError):
        s["wait_service"].plan_wait("", "id")
    with pytest.raises(InvalidAgentTaskRecoveryScheduleDependencyWaitError):
        s["wait_service"].plan_wait("task-1", "")
    with pytest.raises(InvalidAgentTaskRecoveryScheduleDependencyWaitError):
        s["wait_service"].plan_wait("task-1", "never-existed")


def test_apply_wait_rejects_mismatched_plan():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    s["dependency_service"].add_dependency("task-1", dep.task_id)
    _, schedule = _scheduled(s)
    plan = s["wait_service"].plan_wait("task-1", schedule.schedule_id, now=NOW)

    with pytest.raises(InvalidAgentTaskRecoveryScheduleDependencyWaitError):
        s["wait_service"].apply_wait("task-1", "some-other-schedule-id", plan, now=NOW)


def test_apply_wait_rejects_non_plan_object():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    s["dependency_service"].add_dependency("task-1", dep.task_id)
    _, schedule = _scheduled(s)

    with pytest.raises(InvalidAgentTaskRecoveryScheduleDependencyWaitError):
        s["wait_service"].apply_wait("task-1", schedule.schedule_id, "not-a-plan", now=NOW)
