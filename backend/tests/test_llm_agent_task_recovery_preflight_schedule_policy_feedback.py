from datetime import datetime, timedelta, timezone

import pytest

from backend.agent_task_event_analytics import (
    RECOVERY_OUTCOME_FAILED,
    RECOVERY_OUTCOME_SUCCESS,
    AgentTaskFailureRecoveryResult,
    LLMAgentTaskEventFailureClassifier,
    LLMAgentTaskEventFailureRecoveryPlanner,
    LLMAgentTaskRecoveryOutcomeService,
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
    ABANDONED,
    RECOVERED,
    SCHEDULE_FEEDBACK_FAILED,
    DEFAULT_SCHEDULE_EXPIRATION_TTL,
    InvalidAgentTaskRecoveryScheduleFeedbackError,
    LLMAgentTaskRecoveryPreflightScheduleDispatchService,
    LLMAgentTaskRecoveryPreflightScheduleExpirationService,
    LLMAgentTaskRecoveryPreflightSchedulePolicyFeedbackService,
    LLMAgentTaskRecoveryPreflightScheduleValidationService,
    LLMAgentTaskRecoveryPreflightSchedulingService,
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


class _FakeQueueService:
    def enqueue(self, task_id):
        return type("Entry", (), {"task_id": task_id})()


def _stack(with_expiration=False, with_recovery_outcome=False, dispatch_queue_service=None, policy_publisher=None):
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
    schedule_validation_service = LLMAgentTaskRecoveryPreflightScheduleValidationService(
        scheduling_service=scheduling_service, authorization_validation_service=authorization_validation_service,
    )
    dispatch_service = LLMAgentTaskRecoveryPreflightScheduleDispatchService(
        scheduling_service=scheduling_service, validation_service=schedule_validation_service,
        queue_service=dispatch_queue_service,
    )
    expiration_service = None
    if with_expiration:
        expiration_service = LLMAgentTaskRecoveryPreflightScheduleExpirationService(
            scheduling_service=scheduling_service, dispatch_service=dispatch_service,
        )
    recovery_outcome_service = None
    if with_recovery_outcome:
        recovery_outcome_service = LLMAgentTaskRecoveryOutcomeService(event_service=event_service, query_service=query_service)

    feedback_service = LLMAgentTaskRecoveryPreflightSchedulePolicyFeedbackService(
        scheduling_service=scheduling_service, dispatch_service=dispatch_service,
        event_service=event_service, query_service=query_service, expiration_service=expiration_service,
        recovery_outcome_service=recovery_outcome_service, policy_publisher=policy_publisher,
    )
    return {
        "event_service": event_service,
        "invalidation_service": invalidation_service,
        "approval_service": approval_service,
        "preflight_service": preflight_service,
        "preflight_store": preflight_store,
        "scheduling_service": scheduling_service,
        "dispatch_service": dispatch_service,
        "feedback_service": feedback_service,
        "recovery_outcome_service": recovery_outcome_service,
    }


def _fail_task(event_service, task_id="task-1"):
    event_service.emit(task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})
    return event_service.emit(task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": FAILED})


def _scheduled(s, task_id="task-1", execute_at=None):
    _fail_task(s["event_service"], task_id=task_id)
    preflight = s["preflight_store"].save(s["preflight_service"].run(task_id))
    s["approval_service"].request(task_id, preflight.preflight_id)
    s["approval_service"].approve(task_id, preflight.preflight_id, actor="alice")
    return s["scheduling_service"].schedule(task_id, preflight.preflight_id, execute_at=execute_at)


# --- successful outcome --------------------------------------------------------------


def test_record_recovered_outcome_captures_dispatch_evidence():
    s = _stack(dispatch_queue_service=_FakeQueueService())
    schedule = _scheduled(s)
    s["dispatch_service"].dispatch("task-1", schedule.schedule_id)

    feedback = s["feedback_service"].record("task-1", schedule.schedule_id, RECOVERED, now=NOW)

    assert feedback.outcome == RECOVERED
    assert feedback.evidence["dispatched"] is True
    assert feedback.evidence["dispatch_status"] == "dispatched"
    assert feedback.evidence["queue_reference"] is not None
    assert feedback.evidence["time_to_dispatch_seconds"] >= 0


# --- failed outcome --------------------------------------------------------------


def test_record_failed_outcome_for_never_dispatched_schedule():
    s = _stack()
    schedule = _scheduled(s)

    feedback = s["feedback_service"].record("task-1", schedule.schedule_id, SCHEDULE_FEEDBACK_FAILED, now=NOW)

    assert feedback.outcome == SCHEDULE_FEEDBACK_FAILED
    assert feedback.evidence["dispatched"] is False
    assert "dispatch_status" not in feedback.evidence


def test_record_captures_cancellation_evidence():
    s = _stack()
    schedule = _scheduled(s)
    s["scheduling_service"].cancel("task-1", schedule.schedule_id, reason="operator cancelled")

    feedback = s["feedback_service"].record("task-1", schedule.schedule_id, ABANDONED, now=NOW)

    assert feedback.evidence["scheduling_status"] == "cancelled"
    assert feedback.evidence["cancellation_reason"] == "operator cancelled"


# --- missing evidence --------------------------------------------------------------


def test_expiration_evidence_absent_when_not_wired():
    s = _stack(with_expiration=False)
    schedule = _scheduled(s)

    feedback = s["feedback_service"].record("task-1", schedule.schedule_id, ABANDONED, now=NOW)

    assert "expired" not in feedback.evidence


def test_expiration_evidence_present_when_wired():
    ttl = DEFAULT_SCHEDULE_EXPIRATION_TTL
    s = _stack(with_expiration=True)
    schedule = _scheduled(s, execute_at=NOW - ttl - timedelta(minutes=1))

    feedback = s["feedback_service"].record("task-1", schedule.schedule_id, ABANDONED, now=NOW)

    assert feedback.evidence["expired"] is True


def test_eventual_recovery_outcome_absent_when_not_recorded():
    s = _stack(with_recovery_outcome=True)
    schedule = _scheduled(s)

    feedback = s["feedback_service"].record("task-1", schedule.schedule_id, ABANDONED, now=NOW)

    assert "eventual_recovery_status" not in feedback.evidence


def test_eventual_recovery_outcome_present_when_recorded():
    s = _stack(with_recovery_outcome=True)
    schedule = _scheduled(s)
    recovery_result = AgentTaskFailureRecoveryResult(
        task_id="task-1", source_failure_event_id="evt-1", planned_action="retry", executed_action="retry",
        success=True, partial=False, affected_reference=None, failure_reason=None,
    )
    s["recovery_outcome_service"].record("task-1", recovery_result)

    feedback = s["feedback_service"].record("task-1", schedule.schedule_id, RECOVERED, now=NOW)

    assert feedback.evidence["eventual_recovery_status"] == RECOVERY_OUTCOME_SUCCESS


# --- duplicate recording / idempotency --------------------------------------------------------------


def test_duplicate_recording_same_outcome_is_idempotent():
    s = _stack()
    schedule = _scheduled(s)

    first = s["feedback_service"].record("task-1", schedule.schedule_id, ABANDONED, now=NOW)
    second = s["feedback_service"].record("task-1", schedule.schedule_id, ABANDONED, now=NOW + timedelta(hours=1))

    assert first.feedback_id == second.feedback_id
    assert len(s["feedback_service"].list("task-1")) == 1


def test_different_outcome_for_same_schedule_is_a_new_record():
    s = _stack()
    schedule = _scheduled(s)

    first = s["feedback_service"].record("task-1", schedule.schedule_id, SCHEDULE_FEEDBACK_FAILED, now=NOW)
    second = s["feedback_service"].record("task-1", schedule.schedule_id, RECOVERED, now=NOW)

    assert first.feedback_id != second.feedback_id
    assert len(s["feedback_service"].list("task-1")) == 2


# --- integration with existing learning interfaces (publisher hook) --------------------------------------------------------------


def test_policy_publisher_invoked_once_per_new_record():
    published = []
    s = _stack(policy_publisher=published.append)
    schedule = _scheduled(s)

    s["feedback_service"].record("task-1", schedule.schedule_id, ABANDONED, now=NOW)
    s["feedback_service"].record("task-1", schedule.schedule_id, ABANDONED, now=NOW)  # idempotent repeat

    assert len(published) == 1
    assert published[0].outcome == ABANDONED


def test_publisher_failure_does_not_prevent_recording():
    def _broken_publisher(feedback):
        raise RuntimeError("publisher exploded")

    s = _stack(policy_publisher=_broken_publisher)
    schedule = _scheduled(s)

    feedback = s["feedback_service"].record("task-1", schedule.schedule_id, ABANDONED, now=NOW)
    assert feedback is not None
    assert s["feedback_service"].get("task-1", feedback.feedback_id) == feedback


# --- validation / misc --------------------------------------------------------------


def test_invalid_outcome_rejected():
    s = _stack()
    schedule = _scheduled(s)
    with pytest.raises(InvalidAgentTaskRecoveryScheduleFeedbackError):
        s["feedback_service"].record("task-1", schedule.schedule_id, "not-a-real-outcome", now=NOW)


def test_unknown_schedule_id_rejected():
    s = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryScheduleFeedbackError):
        s["feedback_service"].record("task-1", "does-not-exist", ABANDONED, now=NOW)


def test_raw_schedule_history_untouched_by_recording():
    s = _stack()
    schedule = _scheduled(s)

    s["feedback_service"].record("task-1", schedule.schedule_id, ABANDONED, now=NOW)

    after = s["scheduling_service"].get("task-1", schedule.schedule_id)
    assert after == schedule
