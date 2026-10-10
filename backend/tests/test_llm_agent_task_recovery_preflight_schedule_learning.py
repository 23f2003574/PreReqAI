from datetime import datetime, timedelta, timezone

import pytest

from backend.agent_learning_signals import FAILED_STRATEGY, SUCCESSFUL_STRATEGY
from backend.agent_task_event_analytics import (
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
    LEARNED,
    RECOVERED,
    SCHEDULE_FEEDBACK_FAILED,
    SKIPPED_CONTRADICTORY,
    SKIPPED_INSUFFICIENT,
    InvalidAgentTaskRecoveryScheduleLearningError,
    LLMAgentTaskRecoveryPreflightScheduleDispatchService,
    LLMAgentTaskRecoveryPreflightScheduleLearningService,
    LLMAgentTaskRecoveryPreflightSchedulePolicyFeedbackService,
    LLMAgentTaskRecoveryPreflightScheduleReportingService,
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


def _stack(dispatch_queue_service=None, with_recovery_outcome=False, learning_sink=None):
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
    reporting_service = LLMAgentTaskRecoveryPreflightScheduleReportingService(
        scheduling_service=scheduling_service, dispatch_service=dispatch_service,
    )
    recovery_outcome_service = None
    if with_recovery_outcome:
        recovery_outcome_service = LLMAgentTaskRecoveryOutcomeService(event_service=event_service, query_service=query_service)
    feedback_service = LLMAgentTaskRecoveryPreflightSchedulePolicyFeedbackService(
        scheduling_service=scheduling_service, dispatch_service=dispatch_service,
        event_service=event_service, query_service=query_service, recovery_outcome_service=recovery_outcome_service,
    )
    learning_service = LLMAgentTaskRecoveryPreflightScheduleLearningService(
        feedback_service=feedback_service, reporting_service=reporting_service,
        event_service=event_service, query_service=query_service, learning_sink=learning_sink,
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
        "learning_service": learning_service,
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


# --- sufficient successful evidence --------------------------------------------------------------


def test_sufficient_successful_evidence_learns():
    s = _stack(dispatch_queue_service=_FakeQueueService())
    schedule = _scheduled(s)
    s["dispatch_service"].dispatch("task-1", schedule.schedule_id)
    s["feedback_service"].record("task-1", schedule.schedule_id, RECOVERED, now=NOW)

    result = s["learning_service"].learn("task-1")

    assert result.learned_count == 1
    assert result.skipped_count == 0
    assert len(result.signals) == 1
    signal = result.signals[0]
    assert signal.signal_type == SUCCESSFUL_STRATEGY
    assert signal.execution_id == "task-1"
    assert signal.evidence["schedule_id"] == schedule.schedule_id


# --- sufficient failure evidence --------------------------------------------------------------


def test_sufficient_failure_evidence_learns():
    s = _stack()
    schedule = _scheduled(s)
    s["feedback_service"].record("task-1", schedule.schedule_id, SCHEDULE_FEEDBACK_FAILED, now=NOW)

    result = s["learning_service"].learn("task-1")

    assert result.learned_count == 1
    signal = result.signals[0]
    assert signal.signal_type == FAILED_STRATEGY


# --- insufficient evidence --------------------------------------------------------------


def test_abandoned_outcome_is_insufficient():
    s = _stack()
    schedule = _scheduled(s)
    s["feedback_service"].record("task-1", schedule.schedule_id, ABANDONED, now=NOW)

    result = s["learning_service"].learn("task-1")

    assert result.learned_count == 0
    assert result.skipped_count == 1
    assert result.outcomes[0].status == SKIPPED_INSUFFICIENT
    assert result.signals == ()


# --- contradictory evidence --------------------------------------------------------------


def test_recovered_but_never_dispatched_is_contradictory():
    s = _stack()
    schedule = _scheduled(s)  # never dispatched
    s["feedback_service"].record("task-1", schedule.schedule_id, RECOVERED, now=NOW)

    result = s["learning_service"].learn("task-1")

    assert result.learned_count == 0
    assert result.outcomes[0].status == SKIPPED_CONTRADICTORY
    assert "never dispatched" in result.outcomes[0].reason


def test_failed_but_eventual_recovery_succeeded_is_contradictory():
    s = _stack(with_recovery_outcome=True)
    schedule = _scheduled(s)
    recovery_result = AgentTaskFailureRecoveryResult(
        task_id="task-1", source_failure_event_id="evt-1", planned_action="retry", executed_action="retry",
        success=True, partial=False, affected_reference=None, failure_reason=None,
    )
    s["recovery_outcome_service"].record("task-1", recovery_result)
    s["feedback_service"].record("task-1", schedule.schedule_id, SCHEDULE_FEEDBACK_FAILED, now=NOW)

    result = s["learning_service"].learn("task-1")

    assert result.outcomes[0].status == SKIPPED_CONTRADICTORY
    assert RECOVERY_OUTCOME_SUCCESS in result.outcomes[0].reason or "successful" in result.outcomes[0].reason


# --- duplicate learning prevention / idempotency --------------------------------------------------------------


def test_repeated_learn_is_idempotent():
    s = _stack(dispatch_queue_service=_FakeQueueService())
    schedule = _scheduled(s)
    s["dispatch_service"].dispatch("task-1", schedule.schedule_id)
    s["feedback_service"].record("task-1", schedule.schedule_id, RECOVERED, now=NOW)

    first = s["learning_service"].learn("task-1")
    second = s["learning_service"].learn("task-1")

    assert first.learning_id == second.learning_id
    assert len(s["learning_service"].list("task-1")) == 1


def test_new_feedback_after_learning_produces_new_result():
    s = _stack(dispatch_queue_service=_FakeQueueService())
    schedule = _scheduled(s)
    s["dispatch_service"].dispatch("task-1", schedule.schedule_id)
    s["feedback_service"].record("task-1", schedule.schedule_id, RECOVERED, now=NOW)
    first = s["learning_service"].learn("task-1")

    other_schedule = _scheduled(s, task_id="task-1")
    s["feedback_service"].record("task-1", other_schedule.schedule_id, SCHEDULE_FEEDBACK_FAILED, now=NOW)
    second = s["learning_service"].learn("task-1")

    assert second.learning_id != first.learning_id
    assert second.feedback_considered == 2


# --- correct handoff to existing learning services (learning_sink) --------------------------------------------------------------


def test_learning_sink_invoked_once_per_new_result():
    published = []
    s = _stack(dispatch_queue_service=_FakeQueueService(), learning_sink=published.append)
    schedule = _scheduled(s)
    s["dispatch_service"].dispatch("task-1", schedule.schedule_id)
    s["feedback_service"].record("task-1", schedule.schedule_id, RECOVERED, now=NOW)

    s["learning_service"].learn("task-1")
    s["learning_service"].learn("task-1")  # idempotent repeat

    assert len(published) == 1
    assert published[0].learned_count == 1


def test_sink_failure_does_not_prevent_learning():
    def _broken_sink(result):
        raise RuntimeError("sink exploded")

    s = _stack(dispatch_queue_service=_FakeQueueService(), learning_sink=_broken_sink)
    schedule = _scheduled(s)
    s["dispatch_service"].dispatch("task-1", schedule.schedule_id)
    s["feedback_service"].record("task-1", schedule.schedule_id, RECOVERED, now=NOW)

    result = s["learning_service"].learn("task-1")
    assert result is not None
    assert result.learned_count == 1


# --- immutable schedule history / no scheduling/recovery side effects --------------------------------------------------------------


def test_learning_does_not_mutate_schedule_or_feedback():
    s = _stack(dispatch_queue_service=_FakeQueueService())
    schedule = _scheduled(s)
    s["dispatch_service"].dispatch("task-1", schedule.schedule_id)
    feedback_before = s["feedback_service"].record("task-1", schedule.schedule_id, RECOVERED, now=NOW)

    s["learning_service"].learn("task-1")

    schedule_after = s["scheduling_service"].get("task-1", schedule.schedule_id)
    feedback_after = s["feedback_service"].get("task-1", feedback_before.feedback_id)
    assert schedule_after == schedule
    assert feedback_after == feedback_before
    assert len(s["dispatch_service"].list("task-1")) == 1  # no extra dispatch created


def test_scoped_learn_for_unknown_schedule_id_raises():
    s = _stack()
    _scheduled(s)
    with pytest.raises(InvalidAgentTaskRecoveryScheduleLearningError):
        s["learning_service"].learn("task-1", schedule_id="does-not-exist")


def test_blank_task_id_rejected():
    s = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryScheduleLearningError):
        s["learning_service"].learn("")
