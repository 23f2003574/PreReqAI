from types import SimpleNamespace

import pytest

from backend.agent_task_context import UnknownTaskContextError
from backend.agent_task_event_analytics import (
    FAILURE_CATEGORY_CONTEXT,
    FAILURE_CATEGORY_DEPENDENCY,
    InvalidAgentTaskRecoveryRecommendationError,
    LLMAgentTaskEventFailureClassifier,
    LLMAgentTaskEventFailureRecoveryPlanner,
    LLMAgentTaskRecoveryEffectivenessService,
    LLMAgentTaskRecoveryHistoryService,
    LLMAgentTaskRecoveryOutcomeService,
    LLMAgentTaskRecoveryRecommendationService,
    RECOVERY_ACTION_REFRESH_CONTEXT,
    RECOVERY_ACTION_RETRY,
    RECOVERY_ACTION_WAIT_FOR_DEPENDENCY,
    AgentTaskFailureRecoveryResult,
)
from backend.agent_task_events import (
    CONTEXT_UPDATED,
    DEPENDENCY_REMOVED,
    InMemoryAgentTaskEventStore,
    LIFECYCLE_TRANSITIONED,
    LLMAgentTaskEventQueryService,
    LLMAgentTaskEventService,
)
from backend.agent_task_lifecycle import FAILED, PLANNED


class _FakeContextService:
    def __init__(self, exists=True):
        self._exists = exists

    def get(self, task_id):
        if not self._exists:
            raise UnknownTaskContextError(task_id)
        return SimpleNamespace(task_id=task_id)


class _FakeReadinessCheck:
    def __init__(self, name, passed, detail=None):
        self.name = name
        self.passed = passed
        self.detail = detail


class _FakeReadinessResult:
    def __init__(self, checks, blocking_reasons=()):
        self.checks = checks
        self.blocking_reasons = list(blocking_reasons)


class _FakeReadinessService:
    def __init__(self, ready):
        self._ready = ready

    def check(self, task_id):
        if self._ready:
            return _FakeReadinessResult(checks=[_FakeReadinessCheck("dependencies", passed=True)])
        return _FakeReadinessResult(
            checks=[_FakeReadinessCheck("dependencies", passed=False, detail="dependency 'task-0' pending")]
        )


def _stack(planner_collaborators=None):
    store = InMemoryAgentTaskEventStore()
    event_service = LLMAgentTaskEventService(store=store)
    query_service = LLMAgentTaskEventQueryService(store=store)
    classifier = LLMAgentTaskEventFailureClassifier(query_service=query_service)
    outcome_service = LLMAgentTaskRecoveryOutcomeService(event_service=event_service, query_service=query_service)
    history_service = LLMAgentTaskRecoveryHistoryService(outcome_service=outcome_service)
    effectiveness_service = LLMAgentTaskRecoveryEffectivenessService(
        history_service=history_service, failure_classifier=classifier
    )
    planner = LLMAgentTaskEventFailureRecoveryPlanner(classifier=classifier, **(planner_collaborators or {}))
    recommendation_service = LLMAgentTaskRecoveryRecommendationService(
        planner=planner, effectiveness_service=effectiveness_service, classifier=classifier
    )
    return event_service, outcome_service, recommendation_service


def _result(task_id="task-1", **overrides):
    fields = dict(
        task_id=task_id,
        planned_action=RECOVERY_ACTION_REFRESH_CONTEXT,
        executed_action=RECOVERY_ACTION_REFRESH_CONTEXT,
        success=True,
        failure_reason=None,
        affected_reference="context refreshed",
        source_failure_event_id=None,
        partial=False,
    )
    fields.update(overrides)
    return AgentTaskFailureRecoveryResult(**fields)


def _make_context_failure(event_service, task_id="task-1"):
    event_service.emit(task_id, CONTEXT_UPDATED)
    failing = event_service.emit(task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": FAILED})
    return failing


# --- strong historical signal ------------------------------------------------------------------


def test_strong_historical_signal_yields_high_confidence():
    event_service, outcome_service, recommendation_service = _stack(
        planner_collaborators={"context_service": _FakeContextService(exists=True)}
    )
    failing = _make_context_failure(event_service)

    # each call needs to differ in some way, or Commit #5's own content-based
    # idempotency check would collapse identical repeats into one outcome
    for i in range(3):
        outcome_service.record(
            "task-1",
            _result(source_failure_event_id=failing.event_id, success=True, affected_reference=f"attempt {i}"),
        )

    recommendation = recommendation_service.recommend("task-1")

    assert recommendation.recommended_action == RECOVERY_ACTION_REFRESH_CONTEXT
    assert recommendation.confidence == 1.0
    assert len(recommendation.supporting_recovery_ids) == 3


def test_recommend_rejects_blank_task_id():
    _, _, recommendation_service = _stack()

    with pytest.raises(InvalidAgentTaskRecoveryRecommendationError):
        recommendation_service.recommend("")


# --- competing actions -----------------------------------------------------------------------------


def test_competing_actions_use_only_matching_action_evidence():
    event_service, outcome_service, recommendation_service = _stack(
        planner_collaborators={"context_service": _FakeContextService(exists=True)}
    )
    failing = _make_context_failure(event_service)

    # a poor track record for a DIFFERENT action against the same failure
    outcome_service.record(
        "task-1",
        _result(
            source_failure_event_id=failing.event_id,
            planned_action=RECOVERY_ACTION_RETRY,
            executed_action=RECOVERY_ACTION_RETRY,
            success=False,
            failure_reason="not eligible",
            affected_reference=None,
        ),
    )
    # a strong track record for the action the planner will actually recommend
    for i in range(3):
        outcome_service.record(
            "task-1",
            _result(source_failure_event_id=failing.event_id, success=True, affected_reference=f"attempt {i}"),
        )

    recommendation = recommendation_service.recommend("task-1")

    assert recommendation.recommended_action == RECOVERY_ACTION_REFRESH_CONTEXT
    assert recommendation.confidence == 1.0  # unaffected by RETRY's own poor, unrelated track record


# --- no historical data --------------------------------------------------------------------------------


def test_no_historical_data_yields_zero_confidence():
    event_service, _, recommendation_service = _stack(
        planner_collaborators={"context_service": _FakeContextService(exists=True)}
    )
    _make_context_failure(event_service)

    recommendation = recommendation_service.recommend("task-1")

    assert recommendation.recommended_action == RECOVERY_ACTION_REFRESH_CONTEXT
    assert recommendation.confidence == 0.0
    assert recommendation.supporting_recovery_ids == ()
    assert "no prior recovery attempts" in recommendation.reason


# --- low-confidence recommendation ------------------------------------------------------------------------


def test_small_sample_size_dampens_confidence_even_when_fully_successful():
    event_service, outcome_service, recommendation_service = _stack(
        planner_collaborators={"context_service": _FakeContextService(exists=True)}
    )
    failing = _make_context_failure(event_service)
    outcome_service.record("task-1", _result(source_failure_event_id=failing.event_id, success=True))

    recommendation = recommendation_service.recommend("task-1")

    assert 0.0 < recommendation.confidence < 1.0  # 100% success rate, but only 1 of 3 needed samples


def test_mixed_track_record_yields_partial_confidence():
    event_service, outcome_service, recommendation_service = _stack(
        planner_collaborators={"context_service": _FakeContextService(exists=True)}
    )
    failing = _make_context_failure(event_service)
    outcome_service.record(
        "task-1", _result(source_failure_event_id=failing.event_id, success=True, affected_reference="attempt 0")
    )
    outcome_service.record(
        "task-1",
        _result(source_failure_event_id=failing.event_id, success=False, failure_reason="context store down"),
    )
    outcome_service.record(
        "task-1", _result(source_failure_event_id=failing.event_id, success=True, affected_reference="attempt 2")
    )

    recommendation = recommendation_service.recommend("task-1")

    assert recommendation.confidence == pytest.approx(2 / 3)


# --- blocked action ----------------------------------------------------------------------------------------


def test_blocked_action_carries_through_blocking_conditions():
    event_service, _, recommendation_service = _stack(
        planner_collaborators={"readiness_service": _FakeReadinessService(ready=False)}
    )
    event_service.emit("task-1", DEPENDENCY_REMOVED)
    event_service.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": FAILED})

    recommendation = recommendation_service.recommend("task-1")

    assert recommendation.recommended_action == RECOVERY_ACTION_WAIT_FOR_DEPENDENCY
    assert recommendation.blocking_conditions == ("dependency 'task-0' pending",)


# --- current failure differing from historical failures --------------------------------------------------------


def test_evidence_from_a_different_unrecognized_failure_is_excluded_when_classifier_supplied():
    event_service, outcome_service, recommendation_service = _stack(
        planner_collaborators={"context_service": _FakeContextService(exists=True)}
    )
    _make_context_failure(event_service)

    # points at a failure_event_id that was never actually recorded/classified at all
    outcome_service.record("task-1", _result(source_failure_event_id="unrelated-failure-id", success=True))
    outcome_service.record("task-1", _result(source_failure_event_id="unrelated-failure-id", success=True))

    recommendation = recommendation_service.recommend("task-1")

    assert recommendation.confidence == 0.0
    assert recommendation.supporting_recovery_ids == ()


def test_unscoped_history_used_when_no_classifier_supplied():
    store = InMemoryAgentTaskEventStore()
    event_service = LLMAgentTaskEventService(store=store)
    query_service = LLMAgentTaskEventQueryService(store=store)
    outcome_service = LLMAgentTaskRecoveryOutcomeService(event_service=event_service, query_service=query_service)
    history_service = LLMAgentTaskRecoveryHistoryService(outcome_service=outcome_service)
    effectiveness_service = LLMAgentTaskRecoveryEffectivenessService(history_service=history_service)
    planner = LLMAgentTaskEventFailureRecoveryPlanner(
        classifier=LLMAgentTaskEventFailureClassifier(query_service=query_service),
        context_service=_FakeContextService(exists=True),
    )
    recommendation_service = LLMAgentTaskRecoveryRecommendationService(
        planner=planner, effectiveness_service=effectiveness_service, classifier=None
    )
    _make_context_failure(event_service)
    for i in range(3):
        outcome_service.record(
            "task-1",
            _result(source_failure_event_id="unrelated-failure-id", success=True, affected_reference=f"attempt {i}"),
        )

    recommendation = recommendation_service.recommend("task-1")

    assert recommendation.confidence == 1.0  # falls back to unscoped history without a classifier


# --- deterministic repeated recommendation -----------------------------------------------------------------------


def test_repeated_recommendation_is_deterministic():
    event_service, outcome_service, recommendation_service = _stack(
        planner_collaborators={"context_service": _FakeContextService(exists=True)}
    )
    failing = _make_context_failure(event_service)
    outcome_service.record("task-1", _result(source_failure_event_id=failing.event_id, success=True))

    first = recommendation_service.recommend("task-1")
    second = recommendation_service.recommend("task-1")

    assert first == second


def test_no_failure_produces_explicit_no_recommendation():
    event_service, _, recommendation_service = _stack()
    event_service.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})

    recommendation = recommendation_service.recommend("task-1")

    from backend.agent_task_event_analytics import RECOVERY_ACTION_NONE

    assert recommendation.recommended_action == RECOVERY_ACTION_NONE
    assert recommendation.confidence == 0.0
