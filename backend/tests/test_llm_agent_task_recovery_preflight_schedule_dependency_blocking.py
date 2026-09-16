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
    BLOCK_STATUS_BLOCKED,
    BLOCK_STATUS_UNBLOCKED,
    InMemoryAgentTaskRecoveryScheduleDependencyBlockStore,
    InvalidAgentTaskRecoveryScheduleDependencyBlockingError,
    LLMAgentTaskRecoveryPreflightScheduleDependencyBlockingService,
    LLMAgentTaskRecoveryPreflightScheduleDependencyService,
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

    lifecycle_service = LLMAgentTaskLifecycleService()
    dependency_service = LLMAgentTaskDependencyService(lifecycle_service)
    dependency_resolver = LLMAgentTaskDependencyResolver(lifecycle_service, dependency_service)
    gate_service = LLMAgentTaskRecoveryPreflightScheduleDependencyService(
        scheduling_service=scheduling_service, dependency_resolver=dependency_resolver
    )
    blocking_store = InMemoryAgentTaskRecoveryScheduleDependencyBlockStore()
    blocking_service = LLMAgentTaskRecoveryPreflightScheduleDependencyBlockingService(
        dependency_service=gate_service, scheduling_service=scheduling_service,
        validation_service=plain_validation_service, expiration_service=expiration_service,
        store=blocking_store,
    )
    blocking_wired_validation_service = LLMAgentTaskRecoveryPreflightScheduleValidationService(
        scheduling_service=scheduling_service, authorization_validation_service=authorization_validation_service,
        dependency_service=blocking_service,
    )
    dispatch_service = LLMAgentTaskRecoveryPreflightScheduleDispatchService(
        validation_service=blocking_wired_validation_service, scheduling_service=scheduling_service,
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
        "blocking_store": blocking_store,
        "blocking_service": blocking_service,
        "blocking_wired_validation_service": blocking_wired_validation_service,
        "dispatch_service": dispatch_service,
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


# --- blocking ------------------------------------------------------------------------------


def test_block_succeeds_when_dependencies_not_ready():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    s["dependency_service"].add_dependency("task-1", dep.task_id)
    _fail_task(s["event_service"])
    _, schedule = _scheduled(s)

    record = s["blocking_service"].block("task-1", schedule.schedule_id, (dep.task_id,), "waiting on dep")

    assert record.status == BLOCK_STATUS_BLOCKED
    assert record.dependencies == (dep.task_id,)
    assert record.reason == "waiting on dep"
    assert record.evidence != ()


def test_block_rejected_when_dependencies_already_ready():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    s["dependency_service"].add_dependency("task-1", dep.task_id)
    _advance_to(s["lifecycle_service"], dep, COMPLETED)
    _fail_task(s["event_service"])
    _, schedule = _scheduled(s)

    with pytest.raises(InvalidAgentTaskRecoveryScheduleDependencyBlockingError):
        s["blocking_service"].block("task-1", schedule.schedule_id, (dep.task_id,), "should not be allowed")


# --- successful unblocking -------------------------------------------------------------------


def test_successful_unblock_when_dependencies_become_ready():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    s["dependency_service"].add_dependency("task-1", dep.task_id)
    _fail_task(s["event_service"])
    _, schedule = _scheduled(s)
    s["blocking_service"].block("task-1", schedule.schedule_id, (dep.task_id,), "waiting on dep")

    _advance_to(s["lifecycle_service"], dep, COMPLETED)
    record = s["blocking_service"].unblock("task-1", schedule.schedule_id)

    assert record.status == BLOCK_STATUS_UNBLOCKED
    assert record.evidence == ()


# --- unresolved dependencies ------------------------------------------------------------------


def test_unblock_rejected_while_dependencies_still_not_ready():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    s["dependency_service"].add_dependency("task-1", dep.task_id)
    _fail_task(s["event_service"])
    _, schedule = _scheduled(s)
    s["blocking_service"].block("task-1", schedule.schedule_id, (dep.task_id,), "waiting on dep")

    with pytest.raises(InvalidAgentTaskRecoveryScheduleDependencyBlockingError):
        s["blocking_service"].unblock("task-1", schedule.schedule_id)


# --- stale/expired/cancelled/unauthorized schedules --------------------------------------------


def test_unblock_rejected_for_cancelled_schedule():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    s["dependency_service"].add_dependency("task-1", dep.task_id)
    _fail_task(s["event_service"])
    _, schedule = _scheduled(s)
    s["blocking_service"].block("task-1", schedule.schedule_id, (dep.task_id,), "waiting on dep")

    _advance_to(s["lifecycle_service"], dep, COMPLETED)
    s["scheduling_service"].cancel("task-1", schedule.schedule_id, reason="no longer needed")

    with pytest.raises(InvalidAgentTaskRecoveryScheduleDependencyBlockingError):
        s["blocking_service"].unblock("task-1", schedule.schedule_id)


def test_unblock_rejected_for_revoked_authorization():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    s["dependency_service"].add_dependency("task-1", dep.task_id)
    _fail_task(s["event_service"])
    _, schedule = _scheduled(s)
    s["blocking_service"].block("task-1", schedule.schedule_id, (dep.task_id,), "waiting on dep")

    _advance_to(s["lifecycle_service"], dep, COMPLETED)
    s["authorization_service"].revoke("task-1", schedule.authorization_id, reason="revoked externally")

    with pytest.raises(InvalidAgentTaskRecoveryScheduleDependencyBlockingError):
        s["blocking_service"].unblock("task-1", schedule.schedule_id)


def test_unblock_rejected_for_expired_schedule():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    s["dependency_service"].add_dependency("task-1", dep.task_id)
    _fail_task(s["event_service"])
    past = datetime.now(timezone.utc) - timedelta(hours=2)
    _, schedule = _scheduled(s, execute_at=past)
    s["blocking_service"].block("task-1", schedule.schedule_id, (dep.task_id,), "waiting on dep")

    _advance_to(s["lifecycle_service"], dep, COMPLETED)
    expired_service = LLMAgentTaskRecoveryPreflightScheduleExpirationService(
        scheduling_service=s["scheduling_service"], max_overdue_age=timedelta(0)
    )
    blocking_service = LLMAgentTaskRecoveryPreflightScheduleDependencyBlockingService(
        dependency_service=s["gate_service"], scheduling_service=s["scheduling_service"],
        expiration_service=expired_service, store=s["blocking_store"],
    )

    with pytest.raises(InvalidAgentTaskRecoveryScheduleDependencyBlockingError):
        blocking_service.unblock("task-1", schedule.schedule_id)


# --- repeated transitions are idempotent --------------------------------------------------------


def test_repeated_block_is_idempotent():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    s["dependency_service"].add_dependency("task-1", dep.task_id)
    _fail_task(s["event_service"])
    _, schedule = _scheduled(s)

    first = s["blocking_service"].block("task-1", schedule.schedule_id, (dep.task_id,), "waiting on dep")
    second = s["blocking_service"].block("task-1", schedule.schedule_id, (dep.task_id,), "waiting on dep again")

    assert first.block_id == second.block_id
    assert len(s["blocking_service"].get_history("task-1", schedule.schedule_id)) == 1


def test_repeated_unblock_is_idempotent():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    s["dependency_service"].add_dependency("task-1", dep.task_id)
    _fail_task(s["event_service"])
    _, schedule = _scheduled(s)
    s["blocking_service"].block("task-1", schedule.schedule_id, (dep.task_id,), "waiting on dep")
    _advance_to(s["lifecycle_service"], dep, COMPLETED)

    first = s["blocking_service"].unblock("task-1", schedule.schedule_id)
    second = s["blocking_service"].unblock("task-1", schedule.schedule_id)

    assert first.block_id == second.block_id
    assert len(s["blocking_service"].get_history("task-1", schedule.schedule_id)) == 2


def test_unblock_never_blocked_schedule_is_a_noop():
    s = _stack()
    _fail_task(s["event_service"])
    _, schedule = _scheduled(s)

    result = s["blocking_service"].unblock("task-1", schedule.schedule_id)

    assert result is None


# --- history preservation -----------------------------------------------------------------------


def test_history_preserved_across_transitions():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    s["dependency_service"].add_dependency("task-1", dep.task_id)
    _fail_task(s["event_service"])
    _, schedule = _scheduled(s)

    blocked = s["blocking_service"].block("task-1", schedule.schedule_id, (dep.task_id,), "waiting on dep")
    _advance_to(s["lifecycle_service"], dep, COMPLETED)
    unblocked = s["blocking_service"].unblock("task-1", schedule.schedule_id)

    history = s["blocking_service"].get_history("task-1", schedule.schedule_id)
    assert [entry.block_id for entry in history] == [blocked.block_id, unblocked.block_id]
    assert history[0].status == BLOCK_STATUS_BLOCKED
    assert history[1].status == BLOCK_STATUS_UNBLOCKED
    assert history[0].occurred_at <= history[1].occurred_at


# --- dispatch remains impossible while blocked ----------------------------------------------------


def test_dispatch_impossible_while_blocked():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    s["dependency_service"].add_dependency("task-1", dep.task_id)
    _fail_task(s["event_service"])
    _, schedule = _scheduled(s)
    s["blocking_service"].block("task-1", schedule.schedule_id, (dep.task_id,), "waiting on dep")

    validation = s["blocking_wired_validation_service"].validate("task-1", schedule.schedule_id)
    assert validation.valid is False
    with pytest.raises(InvalidAgentTaskRecoveryScheduleDispatchError):
        s["dispatch_service"].dispatch("task-1", schedule.schedule_id)


def test_dispatch_stays_blocked_even_after_dependencies_become_ready_until_explicit_unblock():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    s["dependency_service"].add_dependency("task-1", dep.task_id)
    _fail_task(s["event_service"])
    _, schedule = _scheduled(s)
    s["blocking_service"].block("task-1", schedule.schedule_id, (dep.task_id,), "waiting on dep")

    _advance_to(s["lifecycle_service"], dep, COMPLETED)
    # Live dependency state is now ready, but blocking is sticky.
    still_blocked_validation = s["blocking_wired_validation_service"].validate("task-1", schedule.schedule_id)
    assert still_blocked_validation.valid is False
    with pytest.raises(InvalidAgentTaskRecoveryScheduleDispatchError):
        s["dispatch_service"].dispatch("task-1", schedule.schedule_id)

    s["blocking_service"].unblock("task-1", schedule.schedule_id)

    ready_validation = s["blocking_wired_validation_service"].validate("task-1", schedule.schedule_id)
    assert ready_validation.valid is True
    dispatch = s["dispatch_service"].dispatch("task-1", schedule.schedule_id)
    assert dispatch.status == "dispatched"


# --- status()/check() -----------------------------------------------------------------------------


def test_status_reports_can_unblock_correctly():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    s["dependency_service"].add_dependency("task-1", dep.task_id)
    _fail_task(s["event_service"])
    _, schedule = _scheduled(s)
    s["blocking_service"].block("task-1", schedule.schedule_id, (dep.task_id,), "waiting on dep")

    still_blocked = s["blocking_service"].status("task-1", schedule.schedule_id)
    assert still_blocked.currently_blocked is True
    assert still_blocked.can_unblock is False
    assert still_blocked.unblock_blockers != ()

    _advance_to(s["lifecycle_service"], dep, COMPLETED)
    now_clearable = s["blocking_service"].status("task-1", schedule.schedule_id)
    assert now_clearable.currently_blocked is True
    assert now_clearable.can_unblock is True
    assert now_clearable.unblock_blockers == ()


def test_status_when_never_blocked_reports_ready():
    s = _stack()
    _fail_task(s["event_service"])
    _, schedule = _scheduled(s)

    status = s["blocking_service"].status("task-1", schedule.schedule_id)

    assert status.ready is True
    assert status.currently_blocked is False
    assert status.blockers == ()
    assert status.can_unblock is True


def test_check_bridge_matches_status():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    s["dependency_service"].add_dependency("task-1", dep.task_id)
    _fail_task(s["event_service"])
    _, schedule = _scheduled(s)
    s["blocking_service"].block("task-1", schedule.schedule_id, (dep.task_id,), "waiting on dep")

    checked = s["blocking_service"].check("task-1", schedule.schedule_id)
    status = s["blocking_service"].status("task-1", schedule.schedule_id)

    assert checked.ready == status.ready
    assert checked.blockers == status.blockers


# --- argument validation ---------------------------------------------------------------------------


def test_block_rejects_blank_or_malformed_arguments():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    s["dependency_service"].add_dependency("task-1", dep.task_id)
    _fail_task(s["event_service"])
    _, schedule = _scheduled(s)

    with pytest.raises(InvalidAgentTaskRecoveryScheduleDependencyBlockingError):
        s["blocking_service"].block("", schedule.schedule_id, (dep.task_id,), "reason")
    with pytest.raises(InvalidAgentTaskRecoveryScheduleDependencyBlockingError):
        s["blocking_service"].block("task-1", "", (dep.task_id,), "reason")
    with pytest.raises(InvalidAgentTaskRecoveryScheduleDependencyBlockingError):
        s["blocking_service"].block("task-1", schedule.schedule_id, (dep.task_id,), "")
    with pytest.raises(InvalidAgentTaskRecoveryScheduleDependencyBlockingError):
        s["blocking_service"].block("task-1", schedule.schedule_id, (), "reason")
    with pytest.raises(InvalidAgentTaskRecoveryScheduleDependencyBlockingError):
        s["blocking_service"].block("task-1", schedule.schedule_id, ("",), "reason")
    with pytest.raises(InvalidAgentTaskRecoveryScheduleDependencyBlockingError):
        s["blocking_service"].block("task-1", schedule.schedule_id, "not-a-sequence", "reason")


def test_unblock_rejects_blank_arguments():
    s = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryScheduleDependencyBlockingError):
        s["blocking_service"].unblock("", "id")
    with pytest.raises(InvalidAgentTaskRecoveryScheduleDependencyBlockingError):
        s["blocking_service"].unblock("task-1", "")


# --- never mutates task/schedule state --------------------------------------------------------------


def test_blocking_never_mutates_task_or_schedule_state():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    s["dependency_service"].add_dependency("task-1", dep.task_id)
    _fail_task(s["event_service"])
    _, schedule = _scheduled(s)

    s["blocking_service"].block("task-1", schedule.schedule_id, (dep.task_id,), "waiting on dep")

    assert s["scheduling_service"].get("task-1", schedule.schedule_id).status == "scheduled"
    assert s["lifecycle_service"].get(dep.task_id).current_state == "created"
