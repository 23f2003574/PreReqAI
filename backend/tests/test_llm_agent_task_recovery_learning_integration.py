import pytest

from backend.agent_learning_signals import FAILED_STRATEGY, SUCCESSFUL_STRATEGY
from backend.agent_task_event_analytics import (
    InvalidAgentTaskRecoveryLearningError,
    LLMAgentTaskEventFailureClassifier,
    LLMAgentTaskRecoveryDecisionAuditService,
    LLMAgentTaskRecoveryDecisionComparisonService,
    LLMAgentTaskRecoveryEffectivenessService,
    LLMAgentTaskRecoveryHistoryService,
    LLMAgentTaskRecoveryLearningService,
    LLMAgentTaskRecoveryOutcomeService,
    LLMAgentTaskRecoveryPolicyEffectivenessService,
    LLMAgentTaskRecoveryPolicyFeedbackService,
    RECOVERY_ACTION_REFRESH_CONTEXT,
    AgentTaskFailureRecoveryResult,
    AgentTaskRecoveryPolicyEffectiveness,
    AgentTaskRecoveryRecommendation,
)
from backend.agent_task_events import (
    InMemoryAgentTaskEventStore,
    LIFECYCLE_TRANSITIONED,
    LLMAgentTaskEventQueryService,
    LLMAgentTaskEventService,
)
from backend.agent_task_lifecycle import FAILED, PLANNED
from backend.llm.evaluation_scoring import MAX_SCORE, MIN_SCORE


def _stack():
    store = InMemoryAgentTaskEventStore()
    event_service = LLMAgentTaskEventService(store=store)
    query_service = LLMAgentTaskEventQueryService(store=store)
    classifier = LLMAgentTaskEventFailureClassifier(query_service=query_service)
    outcome_service = LLMAgentTaskRecoveryOutcomeService(event_service=event_service, query_service=query_service)
    history_service = LLMAgentTaskRecoveryHistoryService(outcome_service=outcome_service)
    effectiveness_service = LLMAgentTaskRecoveryEffectivenessService(
        history_service=history_service, failure_classifier=classifier
    )
    audit_service = LLMAgentTaskRecoveryDecisionAuditService(event_service=event_service, query_service=query_service)
    comparison_service = LLMAgentTaskRecoveryDecisionComparisonService(
        audit_service=audit_service, history_service=history_service, effectiveness_service=effectiveness_service
    )
    feedback_service = LLMAgentTaskRecoveryPolicyFeedbackService(
        event_service=event_service, query_service=query_service
    )
    policy_effectiveness_service = LLMAgentTaskRecoveryPolicyEffectivenessService(
        feedback_service=feedback_service, audit_service=audit_service, failure_classifier=classifier
    )
    learning_service = LLMAgentTaskRecoveryLearningService(
        event_service=event_service, query_service=query_service, feedback_service=feedback_service
    )
    return (
        event_service,
        outcome_service,
        audit_service,
        comparison_service,
        feedback_service,
        policy_effectiveness_service,
        learning_service,
    )


def _recommendation(task_id="task-1", **overrides):
    fields = dict(
        task_id=task_id,
        recommended_action=RECOVERY_ACTION_REFRESH_CONTEXT,
        confidence=0.8,
        reason="context refresh has a strong track record",
        supporting_recovery_ids=(),
        blocking_conditions=(),
        failure_event_id="failure-event-1",
    )
    fields.update(overrides)
    return AgentTaskRecoveryRecommendation(**fields)


def _outcome_result(task_id="task-1", **overrides):
    fields = dict(
        task_id=task_id,
        planned_action=RECOVERY_ACTION_REFRESH_CONTEXT,
        executed_action=RECOVERY_ACTION_REFRESH_CONTEXT,
        success=True,
        failure_reason=None,
        affected_reference="context refreshed",
        source_failure_event_id="failure-event-1",
        partial=False,
    )
    fields.update(overrides)
    return AgentTaskFailureRecoveryResult(**fields)


def _illegal_failure(event_service, task_id="task-1"):
    return event_service.emit(task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": FAILED})


def _real_terminal_failure(event_service, task_id="task-1"):
    event_service.emit(task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})
    return event_service.emit(task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": FAILED})


def _feed(task_id, event_service, outcome_service, audit_service, comparison_service, feedback_service, **kwargs):
    effective = kwargs.get("effective", True)
    failing = (
        _illegal_failure(event_service, task_id=task_id)
        if effective
        else _real_terminal_failure(event_service, task_id=task_id)
    )
    success = kwargs.get("success", True)
    audit = audit_service.record(
        task_id, _recommendation(task_id=task_id, failure_event_id=failing.event_id)
    )
    if not kwargs.get("no_recovery", False):
        outcome_service.record(
            task_id,
            _outcome_result(
                task_id=task_id,
                success=success,
                failure_reason=None if success else "did not work",
                affected_reference="done" if success else None,
                source_failure_event_id=failing.event_id,
            ),
        )
    comparison = comparison_service.compare(task_id, decision_id=audit.decision_id)
    return feedback_service.record(task_id, comparison)


def _empty_effectiveness(task_id) -> AgentTaskRecoveryPolicyEffectiveness:
    return AgentTaskRecoveryPolicyEffectiveness(
        task_id=task_id,
        policy_id=None,
        decisions_evaluated=0,
        recommendations_followed=0,
        recommendations_changed=0,
        effective_decisions=0,
        ineffective_decisions=0,
        unknown_outcomes=0,
        effectiveness_rate=None,
        effectiveness_by_action={},
        effectiveness_by_policy={},
        supporting_decision_ids=(),
        supporting_recovery_ids=(),
    )


# --- successful recovery produces a learning signal --------------------------------------------------------------


def test_successful_recovery_produces_a_learning_signal():
    (
        event_service,
        outcome_service,
        audit_service,
        comparison_service,
        feedback_service,
        policy_effectiveness_service,
        learning_service,
    ) = _stack()
    feedback = _feed("task-1", event_service, outcome_service, audit_service, comparison_service, feedback_service)
    effectiveness = policy_effectiveness_service.analyze(task_id="task-1")

    result = learning_service.learn("task-1", effectiveness)

    assert result.task_id == "task-1"
    assert result.decisions_considered == 1
    assert result.skipped_unknown_count == 0
    assert len(result.signals) == 1
    signal = result.signals[0]
    assert signal.signal_type == SUCCESSFUL_STRATEGY
    assert signal.value == MAX_SCORE
    assert signal.execution_id == "task-1"
    assert signal.evidence["decision_id"] == feedback.decision_id
    assert signal.evidence["recovery_id"] == feedback.recovery_id


def test_learn_rejects_blank_task_id():
    *_, learning_service = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryLearningError):
        learning_service.learn("", _empty_effectiveness("task-1"))


def test_learn_rejects_wrong_type():
    *_, learning_service = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryLearningError):
        learning_service.learn("task-1", "not-effectiveness")


def test_learn_rejects_task_id_mismatch():
    *_, learning_service = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryLearningError):
        learning_service.learn("task-1", _empty_effectiveness("task-2"))


# --- failed recovery produces the appropriate negative signal where supported ------------------------------------


def test_failed_recovery_produces_negative_signal():
    (
        event_service,
        outcome_service,
        audit_service,
        comparison_service,
        feedback_service,
        policy_effectiveness_service,
        learning_service,
    ) = _stack()
    _feed(
        "task-1",
        event_service,
        outcome_service,
        audit_service,
        comparison_service,
        feedback_service,
        effective=False,
        success=False,
    )
    effectiveness = policy_effectiveness_service.analyze(task_id="task-1")

    result = learning_service.learn("task-1", effectiveness)

    assert len(result.signals) == 1
    signal = result.signals[0]
    assert signal.signal_type == FAILED_STRATEGY
    assert signal.value == MIN_SCORE


# --- unknown outcome produces no learning update --------------------------------------------------------------


def test_unknown_outcome_produces_no_learning_update():
    (
        event_service,
        outcome_service,
        audit_service,
        comparison_service,
        feedback_service,
        policy_effectiveness_service,
        learning_service,
    ) = _stack()
    _feed(
        "task-1",
        event_service,
        outcome_service,
        audit_service,
        comparison_service,
        feedback_service,
        no_recovery=True,
    )
    effectiveness = policy_effectiveness_service.analyze(task_id="task-1")

    result = learning_service.learn("task-1", effectiveness)

    assert result.signals == ()
    assert result.skipped_unknown_count == 1
    assert result.decisions_considered == 1


def test_mixed_known_and_unknown_only_learns_from_known():
    (
        event_service,
        outcome_service,
        audit_service,
        comparison_service,
        feedback_service,
        policy_effectiveness_service,
        learning_service,
    ) = _stack()
    _feed("task-1", event_service, outcome_service, audit_service, comparison_service, feedback_service)

    failing_2 = event_service.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": FAILED})
    audit_2 = audit_service.record(
        "task-1", _recommendation(task_id="task-1", failure_event_id=failing_2.event_id)
    )
    comparison_2 = comparison_service.compare("task-1", decision_id=audit_2.decision_id)
    feedback_service.record("task-1", comparison_2)  # no corresponding recovery -> unknown

    effectiveness = policy_effectiveness_service.analyze(task_id="task-1")
    result = learning_service.learn("task-1", effectiveness)

    assert result.decisions_considered == 2
    assert result.skipped_unknown_count == 1
    assert len(result.signals) == 1
    assert result.signals[0].signal_type == SUCCESSFUL_STRATEGY


# --- existing learning integration receives correct provenance --------------------------------------------------


def test_learning_sink_receives_correct_provenance():
    (
        event_service,
        outcome_service,
        audit_service,
        comparison_service,
        feedback_service,
        policy_effectiveness_service,
        _,
    ) = _stack()
    received = []
    learning_service = LLMAgentTaskRecoveryLearningService(
        event_service=event_service,
        query_service=LLMAgentTaskEventQueryService(store=event_service.store),
        feedback_service=feedback_service,
        learning_sink=received.append,
    )
    feedback = _feed("task-1", event_service, outcome_service, audit_service, comparison_service, feedback_service)
    effectiveness = policy_effectiveness_service.analyze(task_id="task-1")

    result = learning_service.learn("task-1", effectiveness)
    learning_service.learn("task-1", effectiveness)  # duplicate, must not re-publish

    assert len(received) == 1
    assert received[0] == result
    signal = received[0].signals[0]
    assert signal.evidence["task_id"] == "task-1"
    assert signal.evidence["decision_id"] == feedback.decision_id
    assert signal.evidence["recovery_id"] == feedback.recovery_id
    assert signal.evidence["recommended_action"] == RECOVERY_ACTION_REFRESH_CONTEXT


def test_learning_sink_exception_does_not_prevent_result_from_being_recorded():
    (
        event_service,
        outcome_service,
        audit_service,
        comparison_service,
        feedback_service,
        policy_effectiveness_service,
        _,
    ) = _stack()

    def _broken_sink(result):
        raise RuntimeError("downstream learning system unavailable")

    learning_service = LLMAgentTaskRecoveryLearningService(
        event_service=event_service,
        query_service=LLMAgentTaskEventQueryService(store=event_service.store),
        feedback_service=feedback_service,
        learning_sink=_broken_sink,
    )
    _feed("task-1", event_service, outcome_service, audit_service, comparison_service, feedback_service)
    effectiveness = policy_effectiveness_service.analyze(task_id="task-1")

    result = learning_service.learn("task-1", effectiveness)

    assert len(result.signals) == 1
    assert learning_service.get("task-1").learning_id == result.learning_id


# --- duplicate learning is idempotent --------------------------------------------------------------


def test_duplicate_learning_is_idempotent():
    (
        event_service,
        outcome_service,
        audit_service,
        comparison_service,
        feedback_service,
        policy_effectiveness_service,
        learning_service,
    ) = _stack()
    _feed("task-1", event_service, outcome_service, audit_service, comparison_service, feedback_service)
    effectiveness = policy_effectiveness_service.analyze(task_id="task-1")

    first = learning_service.learn("task-1", effectiveness)
    second = learning_service.learn("task-1", effectiveness)

    assert first == second
    assert len(learning_service.list("task-1")) == 1


def test_new_evidence_produces_a_genuinely_new_learning_result():
    (
        event_service,
        outcome_service,
        audit_service,
        comparison_service,
        feedback_service,
        policy_effectiveness_service,
        learning_service,
    ) = _stack()
    _feed("task-1", event_service, outcome_service, audit_service, comparison_service, feedback_service)
    effectiveness_1 = policy_effectiveness_service.analyze(task_id="task-1")
    learning_service.learn("task-1", effectiveness_1)

    _feed(
        "task-2",
        event_service,
        outcome_service,
        audit_service,
        comparison_service,
        feedback_service,
        effective=False,
        success=False,
    )
    # task-1 unchanged, so re-learning still returns the same one record:
    effectiveness_1_again = policy_effectiveness_service.analyze(task_id="task-1")
    learning_service.learn("task-1", effectiveness_1_again)
    assert len(learning_service.list("task-1")) == 1


# --- unrelated learning records remain unchanged --------------------------------------------------------------


def test_unrelated_task_learning_remains_unaffected():
    (
        event_service,
        outcome_service,
        audit_service,
        comparison_service,
        feedback_service,
        policy_effectiveness_service,
        learning_service,
    ) = _stack()
    _feed("task-1", event_service, outcome_service, audit_service, comparison_service, feedback_service)
    effectiveness_1 = policy_effectiveness_service.analyze(task_id="task-1")
    before = learning_service.learn("task-1", effectiveness_1)

    _feed(
        "task-2",
        event_service,
        outcome_service,
        audit_service,
        comparison_service,
        feedback_service,
        effective=False,
        success=False,
    )
    effectiveness_2 = policy_effectiveness_service.analyze(task_id="task-2")
    learning_service.learn("task-2", effectiveness_2)

    after = learning_service.get("task-1")
    assert before == after
    assert len(learning_service.list("task-1")) == 1
    task_2_result = learning_service.get("task-2")
    assert task_2_result.signals[0].signal_type == FAILED_STRATEGY


def test_learning_does_not_mutate_underlying_feedback_or_audit():
    (
        event_service,
        outcome_service,
        audit_service,
        comparison_service,
        feedback_service,
        policy_effectiveness_service,
        learning_service,
    ) = _stack()
    feedback = _feed("task-1", event_service, outcome_service, audit_service, comparison_service, feedback_service)
    effectiveness = policy_effectiveness_service.analyze(task_id="task-1")

    learning_service.learn("task-1", effectiveness)

    assert feedback_service.get("task-1", feedback_id=feedback.feedback_id) == feedback


# --- deterministic repeated execution --------------------------------------------------------------


def test_deterministic_repeated_get_and_list():
    (
        event_service,
        outcome_service,
        audit_service,
        comparison_service,
        feedback_service,
        policy_effectiveness_service,
        learning_service,
    ) = _stack()
    _feed("task-1", event_service, outcome_service, audit_service, comparison_service, feedback_service)
    effectiveness = policy_effectiveness_service.analyze(task_id="task-1")
    learning_service.learn("task-1", effectiveness)

    assert learning_service.get("task-1") == learning_service.get("task-1")
    assert learning_service.list("task-1") == learning_service.list("task-1")


def test_get_and_list_empty_for_task_with_no_learning():
    *_, learning_service = _stack()

    assert learning_service.get("task-1") is None
    assert learning_service.list("task-1") == []
