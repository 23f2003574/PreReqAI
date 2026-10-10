import pytest

from backend.agent_task_dependencies import LLMAgentTaskDependencyService, TaskDependency
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
    CREATED,
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
    BLOCKED as DEP_BLOCKED,
    FAILED as DEP_FAILED,
    READY as DEP_READY,
    UNKNOWN as DEP_UNKNOWN,
    InvalidAgentTaskRecoveryScheduleDependencyError,
    LLMAgentTaskRecoveryPreflightScheduleDependencyService,
)
from backend.agent_task_recovery_scheduling import (
    InvalidAgentTaskRecoveryScheduleDispatchError,
    LLMAgentTaskRecoveryPreflightScheduleDispatchService,
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


def _stack(readiness=None):
    store = InMemoryAgentTaskEventStore()
    event_service = LLMAgentTaskEventService(store=store)
    query_service = LLMAgentTaskEventQueryService(store=store)
    classifier = LLMAgentTaskEventFailureClassifier(query_service=query_service)
    replay_service = LLMAgentTaskEventReplayService(query_service=query_service)

    readiness = readiness if readiness is not None else _FakeReadinessService()
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

    lifecycle_service = LLMAgentTaskLifecycleService()
    dependency_service = LLMAgentTaskDependencyService(lifecycle_service)
    dependency_resolver = LLMAgentTaskDependencyResolver(lifecycle_service, dependency_service)
    gate_service = LLMAgentTaskRecoveryPreflightScheduleDependencyService(
        scheduling_service=scheduling_service, dependency_resolver=dependency_resolver
    )
    schedule_validation_service = LLMAgentTaskRecoveryPreflightScheduleValidationService(
        scheduling_service=scheduling_service, authorization_validation_service=authorization_validation_service,
        dependency_service=gate_service,
    )
    dispatch_service = LLMAgentTaskRecoveryPreflightScheduleDispatchService(
        validation_service=schedule_validation_service, scheduling_service=scheduling_service,
    )

    lifecycle_service.create(_definition(task_id="task-1"))

    return {
        "event_service": event_service,
        "readiness": readiness,
        "preflight_service": preflight_service,
        "preflight_store": preflight_store,
        "invalidation_service": invalidation_service,
        "approval_service": approval_service,
        "authorization_service": authorization_service,
        "scheduling_service": scheduling_service,
        "authorization_validation_service": authorization_validation_service,
        "schedule_validation_service": schedule_validation_service,
        "dispatch_service": dispatch_service,
        "lifecycle_service": lifecycle_service,
        "dependency_service": dependency_service,
        "dependency_resolver": dependency_resolver,
        "gate_service": gate_service,
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


# --- ready dependencies --------------------------------------------------------------


def test_no_dependencies_reports_ready():
    s = _stack()
    _fail_task(s["event_service"])
    _, schedule = _scheduled(s)

    result = s["gate_service"].check("task-1", schedule.schedule_id)

    assert result.ready is True
    assert result.state == DEP_READY
    assert result.blockers == ()
    assert result.preflight_id == schedule.preflight_id
    assert s["gate_service"].is_ready("task-1", schedule.schedule_id) is True


def test_completed_dependency_reports_ready():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    s["dependency_service"].add_dependency("task-1", dep.task_id)
    _advance_to(s["lifecycle_service"], dep, COMPLETED)
    _fail_task(s["event_service"])
    _, schedule = _scheduled(s)

    result = s["gate_service"].check("task-1", schedule.schedule_id)

    assert result.ready is True
    assert result.state == DEP_READY
    assert result.blockers == ()


# --- blocked (pending) dependencies -----------------------------------------------------


def test_pending_dependency_reports_blocked():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    s["dependency_service"].add_dependency("task-1", dep.task_id)
    _fail_task(s["event_service"])
    _, schedule = _scheduled(s)

    result = s["gate_service"].check("task-1", schedule.schedule_id)

    assert result.ready is False
    assert result.state == DEP_BLOCKED
    # A dependency with no dependencies of its own is the resolver's own
    # frontier bucket (ready_dependencies) -- not yet COMPLETED, merely
    # unblocked to start; the gate still treats it as outstanding.
    assert dep.task_id in result.ready_dependencies
    assert any(dep.task_id in reason for reason in result.blockers)
    assert s["gate_service"].is_ready("task-1", schedule.schedule_id) is False


# --- failed dependencies -----------------------------------------------------------------


def test_failed_dependency_reports_failed():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    s["dependency_service"].add_dependency("task-1", dep.task_id)
    _advance_to(s["lifecycle_service"], dep, FAILED)
    _fail_task(s["event_service"])
    _, schedule = _scheduled(s)

    result = s["gate_service"].check("task-1", schedule.schedule_id)

    assert result.ready is False
    assert result.state == DEP_FAILED
    assert dep.task_id in result.failed_dependencies


def test_transitively_blocked_dependency_reports_failed_root_cause():
    s = _stack()
    mid = _task(s["lifecycle_service"])
    leaf = _task(s["lifecycle_service"])
    s["dependency_service"].add_dependency("task-1", mid.task_id)
    s["dependency_service"].add_dependency(mid.task_id, leaf.task_id)
    _advance_to(s["lifecycle_service"], leaf, FAILED)
    _fail_task(s["event_service"])
    _, schedule = _scheduled(s)

    result = s["gate_service"].check("task-1", schedule.schedule_id)

    assert result.ready is False
    assert result.state == DEP_FAILED
    assert leaf.task_id in result.failed_dependencies
    assert mid.task_id in result.blocked_dependencies


def test_cycle_reports_failed():
    s = _stack()
    dep_a = _task(s["lifecycle_service"])
    dep_b = _task(s["lifecycle_service"])
    s["dependency_service"].add_dependency("task-1", dep_a.task_id)
    s["dependency_service"].add_dependency(dep_a.task_id, dep_b.task_id)
    # Force a cycle directly into the store, bypassing add_dependency()'s
    # own write-time cycle guard -- the same defensive scenario Commit #6's
    # own resolver already protects against.
    s["dependency_service"].store.save(TaskDependency(task_id=dep_b.task_id, dependency_task_id=dep_a.task_id))
    _fail_task(s["event_service"])
    _, schedule = _scheduled(s)

    result = s["gate_service"].check("task-1", schedule.schedule_id)

    assert result.ready is False
    assert result.state == DEP_FAILED
    assert sorted(result.cycles) == sorted([dep_a.task_id, dep_b.task_id])


# --- unknown dependency state --------------------------------------------------------------


def test_unresolved_dependency_reports_unknown():
    s = _stack()
    # Simulate a store edited outside Commit #5, referencing a task that
    # was never actually created.
    s["dependency_service"].store.save(TaskDependency(task_id="task-1", dependency_task_id="ghost-task"))
    _fail_task(s["event_service"])
    _, schedule = _scheduled(s)

    result = s["gate_service"].check("task-1", schedule.schedule_id)

    assert result.ready is False
    assert result.state == DEP_UNKNOWN
    assert "ghost-task" in result.unresolved_dependencies


# --- dependency state changes after scheduling ---------------------------------------------


def test_dependency_state_is_re_checked_not_trusted_from_scheduling_time():
    s = _stack()
    _fail_task(s["event_service"])
    _, schedule = _scheduled(s)

    before = s["gate_service"].check("task-1", schedule.schedule_id)
    assert before.ready is True

    # A brand-new dependency edge is introduced *after* this exact schedule
    # already exists -- scheduling-time data could never have seen it.
    new_dep = s["lifecycle_service"].create(_definition())
    s["dependency_service"].add_dependency("task-1", new_dep.task_id)

    after = s["gate_service"].check("task-1", schedule.schedule_id)
    assert after.ready is False
    assert after.state == DEP_BLOCKED
    assert new_dep.task_id in after.ready_dependencies


# --- schedule/preflight binding ---------------------------------------------------------


def test_schedule_from_wrong_task_reports_unknown_and_not_ready():
    s = _stack()
    s["lifecycle_service"].create(_definition(task_id="task-2"))
    _fail_task(s["event_service"])
    _, schedule = _scheduled(s, task_id="task-1")

    result = s["gate_service"].check("task-2", schedule.schedule_id)

    assert result.ready is False
    assert result.state == DEP_UNKNOWN
    assert result.preflight_id is None


def test_missing_schedule_reports_unknown_and_not_ready():
    s = _stack()

    result = s["gate_service"].check("task-1", "never-existed")

    assert result.ready is False
    assert result.state == DEP_UNKNOWN
    assert result.preflight_id is None


def test_result_is_bound_to_the_exact_preflight():
    s = _stack()
    _fail_task(s["event_service"])
    preflight, schedule = _scheduled(s)

    result = s["gate_service"].check("task-1", schedule.schedule_id)

    assert result.task_id == "task-1"
    assert result.schedule_id == schedule.schedule_id
    assert result.preflight_id == preflight.preflight_id


# --- argument validation ------------------------------------------------------------------


def test_check_rejects_blank_arguments():
    s = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryScheduleDependencyError):
        s["gate_service"].check("", "id")
    with pytest.raises(InvalidAgentTaskRecoveryScheduleDependencyError):
        s["gate_service"].check("task-1", "")


# --- deterministic, idempotent, read-only --------------------------------------------------


def test_deterministic_repeated_check():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    s["dependency_service"].add_dependency("task-1", dep.task_id)
    _fail_task(s["event_service"])
    _, schedule = _scheduled(s)

    first = s["gate_service"].check("task-1", schedule.schedule_id)
    second = s["gate_service"].check("task-1", schedule.schedule_id)

    assert first.ready == second.ready
    assert first.state == second.state
    assert first.blockers == second.blockers


def test_check_never_mutates_dependency_or_schedule_state():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    s["dependency_service"].add_dependency("task-1", dep.task_id)
    _fail_task(s["event_service"])
    _, schedule = _scheduled(s)

    s["gate_service"].check("task-1", schedule.schedule_id)

    assert s["lifecycle_service"].get(dep.task_id).current_state == CREATED
    assert s["scheduling_service"].get("task-1", schedule.schedule_id).status == "scheduled"


# --- integration into the existing schedule validation/dispatch path -----------------------


def test_ready_dependencies_allow_successful_dispatch_eligibility():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    s["dependency_service"].add_dependency("task-1", dep.task_id)
    _advance_to(s["lifecycle_service"], dep, COMPLETED)
    _fail_task(s["event_service"])
    _, schedule = _scheduled(s)

    validation = s["schedule_validation_service"].validate("task-1", schedule.schedule_id)
    assert validation.valid is True

    dispatch = s["dispatch_service"].dispatch("task-1", schedule.schedule_id)
    assert dispatch.status == "dispatched"


def test_pending_dependency_prevents_dispatch():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    s["dependency_service"].add_dependency("task-1", dep.task_id)
    _fail_task(s["event_service"])
    _, schedule = _scheduled(s)

    validation = s["schedule_validation_service"].validate("task-1", schedule.schedule_id)
    assert validation.valid is False
    assert any("has not completed yet" in reason for reason in validation.blocking_reasons)

    with pytest.raises(InvalidAgentTaskRecoveryScheduleDispatchError):
        s["dispatch_service"].dispatch("task-1", schedule.schedule_id)


def test_failed_dependency_prevents_dispatch():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    s["dependency_service"].add_dependency("task-1", dep.task_id)
    _advance_to(s["lifecycle_service"], dep, FAILED)
    _fail_task(s["event_service"])
    _, schedule = _scheduled(s)

    validation = s["schedule_validation_service"].validate("task-1", schedule.schedule_id)
    assert validation.valid is False
    assert any("failed or was cancelled" in reason for reason in validation.blocking_reasons)

    with pytest.raises(InvalidAgentTaskRecoveryScheduleDispatchError):
        s["dispatch_service"].dispatch("task-1", schedule.schedule_id)


def test_blocked_dependency_prevents_dispatch():
    s = _stack()
    mid = _task(s["lifecycle_service"])
    leaf = _task(s["lifecycle_service"])
    s["dependency_service"].add_dependency("task-1", mid.task_id)
    s["dependency_service"].add_dependency(mid.task_id, leaf.task_id)
    _advance_to(s["lifecycle_service"], leaf, FAILED)
    _fail_task(s["event_service"])
    _, schedule = _scheduled(s)

    validation = s["schedule_validation_service"].validate("task-1", schedule.schedule_id)
    assert validation.valid is False
    assert any("blocked by an upstream failure" in reason for reason in validation.blocking_reasons)

    with pytest.raises(InvalidAgentTaskRecoveryScheduleDispatchError):
        s["dispatch_service"].dispatch("task-1", schedule.schedule_id)


def test_validation_service_without_dependency_gate_is_unaffected():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    s["dependency_service"].add_dependency("task-1", dep.task_id)
    _fail_task(s["event_service"])
    _, schedule = _scheduled(s)

    # A validation service built with no dependency_service at all (the
    # default) never runs this gate -- existing callers see no change,
    # even though the exact same schedule has a still-pending dependency.
    bare_validation_service = LLMAgentTaskRecoveryPreflightScheduleValidationService(
        scheduling_service=s["scheduling_service"],
        authorization_validation_service=s["authorization_validation_service"],
    )

    validation = bare_validation_service.validate("task-1", schedule.schedule_id)
    assert validation.valid is True
