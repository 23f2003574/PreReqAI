from datetime import datetime, timedelta, timezone

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
    DISPATCHED,
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


class _FakeQueueEntry:
    def __init__(self, task_id):
        self.task_id = task_id


class _FakeQueueService:
    def __init__(self):
        self.enqueued = []

    def enqueue(self, task_id):
        self.enqueued.append(task_id)
        return _FakeQueueEntry(task_id)


class _BrokenQueueService:
    def enqueue(self, task_id):
        raise RuntimeError("queue backend unavailable")


def _stack(readiness=None, queue_service=None):
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
    dispatch_service = LLMAgentTaskRecoveryPreflightScheduleDispatchService(
        validation_service=schedule_validation_service, scheduling_service=scheduling_service,
        queue_service=queue_service,
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


# --- eligible dispatch --------------------------------------------------------------


def test_eligible_dispatch_succeeds():
    s = _stack()
    _fail_task(s["event_service"])
    preflight, schedule = _scheduled(s)

    dispatch = s["dispatch_service"].dispatch("task-1", schedule.schedule_id)

    assert dispatch.status == DISPATCHED
    assert dispatch.task_id == "task-1"
    assert dispatch.schedule_id == schedule.schedule_id
    assert dispatch.preflight_id == preflight.preflight_id
    assert dispatch.queue_reference is None  # no queue collaborator supplied


def test_dispatch_rejects_blank_arguments():
    s = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryScheduleDispatchError):
        s["dispatch_service"].dispatch("", "id")
    with pytest.raises(InvalidAgentTaskRecoveryScheduleDispatchError):
        s["dispatch_service"].dispatch("task-1", "")


# --- early dispatch rejection --------------------------------------------------------------


def test_early_dispatch_is_rejected():
    s = _stack()
    _fail_task(s["event_service"])
    preflight, schedule = _scheduled(s, execute_at=datetime.now(timezone.utc) + timedelta(hours=1))

    with pytest.raises(InvalidAgentTaskRecoveryScheduleDispatchError):
        s["dispatch_service"].dispatch("task-1", schedule.schedule_id)
    assert s["dispatch_service"].get("task-1", "anything") is None


# --- stale/invalid schedule rejection --------------------------------------------------------------


def test_invalidated_schedule_is_rejected():
    s = _stack()
    _fail_task(s["event_service"])
    preflight, schedule = _scheduled(s)
    s["invalidation_service"].invalidate("task-1", reason="operator flagged this")

    with pytest.raises(InvalidAgentTaskRecoveryScheduleDispatchError):
        s["dispatch_service"].dispatch("task-1", schedule.schedule_id)


def test_revoked_authorization_schedule_is_rejected():
    s = _stack()
    _fail_task(s["event_service"])
    preflight, schedule = _scheduled(s)
    s["authorization_service"].revoke("task-1", schedule.authorization_id, reason="revoked externally")

    with pytest.raises(InvalidAgentTaskRecoveryScheduleDispatchError):
        s["dispatch_service"].dispatch("task-1", schedule.schedule_id)


def test_missing_schedule_is_rejected():
    s = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryScheduleDispatchError):
        s["dispatch_service"].dispatch("task-1", "never-existed")


# --- duplicate dispatch prevention --------------------------------------------------------------


def test_duplicate_dispatch_returns_same_record():
    s = _stack()
    _fail_task(s["event_service"])
    preflight, schedule = _scheduled(s)

    first = s["dispatch_service"].dispatch("task-1", schedule.schedule_id)
    second = s["dispatch_service"].dispatch("task-1", schedule.schedule_id)

    assert first.dispatch_id == second.dispatch_id


# --- cancellation --------------------------------------------------------------


def test_cancelled_schedule_cannot_dispatch():
    s = _stack()
    _fail_task(s["event_service"])
    preflight, schedule = _scheduled(s)
    s["scheduling_service"].cancel("task-1", schedule.schedule_id, reason="no longer needed")

    with pytest.raises(InvalidAgentTaskRecoveryScheduleDispatchError):
        s["dispatch_service"].dispatch("task-1", schedule.schedule_id)


# --- correct task/preflight binding --------------------------------------------------------------


def test_dispatch_bound_to_exact_task_and_preflight():
    s = _stack()
    _fail_task(s["event_service"])
    preflight, schedule = _scheduled(s)
    dispatch = s["dispatch_service"].dispatch("task-1", schedule.schedule_id)

    assert s["dispatch_service"].get("task-2", dispatch.dispatch_id) is None
    assert s["dispatch_service"].get("task-1", dispatch.dispatch_id).preflight_id == preflight.preflight_id


# --- persistence --------------------------------------------------------------


def test_dispatch_history_lists_all():
    s = _stack()
    _fail_task(s["event_service"])
    preflight, schedule = _scheduled(s)
    s["dispatch_service"].dispatch("task-1", schedule.schedule_id)

    history = s["dispatch_service"].list("task-1")
    assert len(history) == 1
    assert history[0].schedule_id == schedule.schedule_id


def test_list_and_get_empty_for_unknown():
    s = _stack()
    assert s["dispatch_service"].list("task-1") == []
    assert s["dispatch_service"].get("task-1", "never-existed") is None


# --- handoff to existing queue/dispatcher --------------------------------------------------------------


def test_handoff_to_real_queue_collaborator():
    queue = _FakeQueueService()
    s = _stack(queue_service=queue)
    _fail_task(s["event_service"])
    preflight, schedule = _scheduled(s)

    dispatch = s["dispatch_service"].dispatch("task-1", schedule.schedule_id)

    assert queue.enqueued == ["task-1"]
    assert dispatch.queue_reference == "task-1"


def test_queue_failure_prevents_dispatch_record():
    s = _stack(queue_service=_BrokenQueueService())
    _fail_task(s["event_service"])
    preflight, schedule = _scheduled(s)

    with pytest.raises(InvalidAgentTaskRecoveryScheduleDispatchError):
        s["dispatch_service"].dispatch("task-1", schedule.schedule_id)
    assert s["dispatch_service"].list("task-1") == []
