import pytest

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
from backend.agent_task_lifecycle import FAILED, PLANNED
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
from backend.agent_task_recovery_scheduling import (
    ADMITTED,
    InvalidAgentTaskRecoveryScheduleCapacityError,
    LLMAgentTaskRecoveryPreflightScheduleCapacityService,
    LLMAgentTaskRecoveryPreflightSchedulingService,
    LLMAgentTaskRecoveryPreflightScheduleValidationService,
)
from backend.session import ExecutionConcurrencyService


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


def _stack(readiness=None, concurrency_service=None, max_running=None):
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
    schedule_validation_service = LLMAgentTaskRecoveryPreflightScheduleValidationService(
        scheduling_service=scheduling_service, authorization_validation_service=authorization_validation_service,
    )
    capacity_service = LLMAgentTaskRecoveryPreflightScheduleCapacityService(
        validation_service=schedule_validation_service, concurrency_service=concurrency_service,
        max_running=max_running,
    )
    return {
        "event_service": event_service,
        "readiness": readiness,
        "preflight_service": preflight_service,
        "preflight_store": preflight_store,
        "invalidation_service": invalidation_service,
        "approval_service": approval_service,
        "authorization_service": authorization_service,
        "scheduling_service": scheduling_service,
        "capacity_service": capacity_service,
    }


def _fail_task(event_service, task_id="task-1"):
    event_service.emit(task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})
    return event_service.emit(task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": FAILED})


def _scheduled(s, task_id="task-1"):
    _fail_task(s["event_service"], task_id=task_id)
    preflight = s["preflight_store"].save(s["preflight_service"].run(task_id))
    s["approval_service"].request(task_id, preflight.preflight_id)
    s["approval_service"].approve(task_id, preflight.preflight_id, actor="alice")
    return s["scheduling_service"].schedule(task_id, preflight.preflight_id)


# --- available capacity --------------------------------------------------------------


def test_available_capacity_admits():
    s = _stack()  # no concurrency_service -> always available
    schedule = _scheduled(s)

    check = s["capacity_service"].check("task-1", schedule.schedule_id)
    assert check.capacity_available is True
    assert check.eligible is True
    assert check.blocking_reasons == ()

    admission = s["capacity_service"].admit("task-1", schedule.schedule_id)
    assert admission.status == ADMITTED


def test_check_rejects_blank_task_id():
    s = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryScheduleCapacityError):
        s["capacity_service"].check("")


# --- exhausted capacity / budget/concurrency limits --------------------------------------------------------------


def test_exhausted_capacity_blocks_admission():
    concurrency = ExecutionConcurrencyService()
    s = _stack(concurrency_service=concurrency, max_running=1)
    first = _scheduled(s, task_id="task-1")
    second_readiness = _FakeReadinessService()

    s["capacity_service"].admit("task-1", first.schedule_id)

    # A second, distinct task's schedule now finds no spare capacity.
    second = _scheduled(s, task_id="task-2")
    check = s["capacity_service"].check("task-2", second.schedule_id)
    assert check.capacity_available is False
    assert any("no spare execution capacity" in r for r in check.blocking_reasons)

    with pytest.raises(InvalidAgentTaskRecoveryScheduleCapacityError):
        s["capacity_service"].admit("task-2", second.schedule_id)


# --- competing schedules --------------------------------------------------------------


def test_competing_schedules_only_first_admitted():
    concurrency = ExecutionConcurrencyService()
    s = _stack(concurrency_service=concurrency, max_running=1)
    a = _scheduled(s, task_id="task-a")
    b = _scheduled(s, task_id="task-b")

    admitted_a = s["capacity_service"].admit("task-a", a.schedule_id)
    assert admitted_a.status == ADMITTED

    with pytest.raises(InvalidAgentTaskRecoveryScheduleCapacityError):
        s["capacity_service"].admit("task-b", b.schedule_id)


# --- invalid schedules --------------------------------------------------------------


def test_cancelled_schedule_cannot_be_admitted():
    s = _stack()
    schedule = _scheduled(s)
    s["scheduling_service"].cancel("task-1", schedule.schedule_id)

    check = s["capacity_service"].check("task-1", schedule.schedule_id)
    assert check.eligible is False

    with pytest.raises(InvalidAgentTaskRecoveryScheduleCapacityError):
        s["capacity_service"].admit("task-1", schedule.schedule_id)


def test_invalidated_schedule_cannot_be_admitted():
    s = _stack()
    schedule = _scheduled(s)
    s["invalidation_service"].invalidate("task-1", reason="operator flagged this")

    with pytest.raises(InvalidAgentTaskRecoveryScheduleCapacityError):
        s["capacity_service"].admit("task-1", schedule.schedule_id)


# --- repeated admission --------------------------------------------------------------


def test_repeated_admission_is_idempotent():
    concurrency = ExecutionConcurrencyService()
    s = _stack(concurrency_service=concurrency, max_running=1)
    schedule = _scheduled(s)

    first = s["capacity_service"].admit("task-1", schedule.schedule_id)
    second = s["capacity_service"].admit("task-1", schedule.schedule_id)

    assert first.admission_id == second.admission_id
    assert concurrency.can_start("agent_task_recovery") is False  # only ONE slot ever consumed


# --- changing capacity between checks --------------------------------------------------------------


def test_capacity_recheck_reflects_freed_slot():
    concurrency = ExecutionConcurrencyService()
    s = _stack(concurrency_service=concurrency, max_running=1)
    a = _scheduled(s, task_id="task-a")
    b = _scheduled(s, task_id="task-b")

    s["capacity_service"].admit("task-a", a.schedule_id)
    assert s["capacity_service"].check("task-b", b.schedule_id).capacity_available is False

    concurrency.release("agent_task_recovery", a.schedule_id)

    assert s["capacity_service"].check("task-b", b.schedule_id).capacity_available is True
    admitted_b = s["capacity_service"].admit("task-b", b.schedule_id)
    assert admitted_b.status == ADMITTED


# --- proof admission never executes recovery --------------------------------------------------------------


def test_admission_never_mutates_task_or_authorization_state():
    s = _stack()
    schedule = _scheduled(s)
    before = s["authorization_service"].get("task-1", schedule.authorization_id)

    s["capacity_service"].admit("task-1", schedule.schedule_id)

    after = s["authorization_service"].get("task-1", schedule.authorization_id)
    assert before == after
    assert before.status == "active"
