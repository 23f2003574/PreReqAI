import pytest

from backend.agent_task_event_analytics import (
    InvalidAgentTaskRecoveryPolicyEffectivenessError,
    LLMAgentTaskEventFailureClassifier,
    LLMAgentTaskRecoveryDecisionAuditService,
    LLMAgentTaskRecoveryDecisionComparisonService,
    LLMAgentTaskRecoveryEffectivenessService,
    LLMAgentTaskRecoveryHistoryService,
    LLMAgentTaskRecoveryOutcomeService,
    LLMAgentTaskRecoveryPolicyEffectivenessService,
    LLMAgentTaskRecoveryPolicyFeedbackService,
    RECOVERY_ACTION_MARK_UNRECOVERABLE,
    RECOVERY_ACTION_REFRESH_CONTEXT,
    RECOVERY_ACTION_RETRY,
    AgentTaskFailureRecoveryResult,
    AgentTaskRecoveryRecommendation,
)
from backend.agent_task_events import (
    InMemoryAgentTaskEventStore,
    LIFECYCLE_TRANSITIONED,
    LLMAgentTaskEventQueryService,
    LLMAgentTaskEventService,
)
from backend.agent_task_lifecycle import FAILED, PLANNED


def _stack(with_classifier=True):
    store = InMemoryAgentTaskEventStore()
    event_service = LLMAgentTaskEventService(store=store)
    query_service = LLMAgentTaskEventQueryService(store=store)
    classifier = LLMAgentTaskEventFailureClassifier(query_service=query_service) if with_classifier else None
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
    return (
        event_service,
        outcome_service,
        audit_service,
        comparison_service,
        feedback_service,
        policy_effectiveness_service,
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
    """Drive one task through decision -> outcome -> comparison ->
    feedback, returning the recorded feedback record."""
    failing = _illegal_failure(event_service, task_id=task_id) if kwargs.get("effective", True) else _real_terminal_failure(
        event_service, task_id=task_id
    )
    recommended_action = kwargs.get("recommended_action", RECOVERY_ACTION_REFRESH_CONTEXT)
    executed_action = kwargs.get("executed_action", recommended_action)
    success = kwargs.get("success", True)
    audit = audit_service.record(
        task_id,
        _recommendation(
            task_id=task_id,
            recommended_action=recommended_action,
            confidence=kwargs.get("confidence", 0.8),
            failure_event_id=failing.event_id,
        ),
    )
    if kwargs.get("no_recovery", False):
        pass
    else:
        outcome_service.record(
            task_id,
            _outcome_result(
                task_id=task_id,
                planned_action=recommended_action,
                executed_action=executed_action,
                success=success,
                failure_reason=None if success else "did not work",
                affected_reference="done" if success else None,
                source_failure_event_id=failing.event_id,
            ),
        )
    comparison = comparison_service.compare(task_id, decision_id=audit.decision_id)
    feedback = feedback_service.record(task_id, comparison)
    return feedback


# --- all-effective decisions --------------------------------------------------------------


def test_all_effective_decisions():
    event_service, outcome_service, audit_service, comparison_service, feedback_service, policy_service = _stack()
    _feed("task-1", event_service, outcome_service, audit_service, comparison_service, feedback_service)
    _feed("task-2", event_service, outcome_service, audit_service, comparison_service, feedback_service)

    result = policy_service.analyze()

    assert result.decisions_evaluated == 2
    assert result.effective_decisions == 2
    assert result.ineffective_decisions == 0
    assert result.unknown_outcomes == 0
    assert result.effectiveness_rate == 1.0
    assert result.recommendations_followed == 2
    assert result.recommendations_changed == 0
    assert len(result.supporting_decision_ids) == 2


# --- mixed outcomes --------------------------------------------------------------


def test_mixed_outcomes():
    event_service, outcome_service, audit_service, comparison_service, feedback_service, policy_service = _stack()
    _feed("task-1", event_service, outcome_service, audit_service, comparison_service, feedback_service, effective=True, success=True)
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

    result = policy_service.analyze()

    assert result.decisions_evaluated == 2
    assert result.effective_decisions == 1
    assert result.ineffective_decisions == 1
    assert result.unknown_outcomes == 0
    assert result.effectiveness_rate == 0.5


# --- rejected recommendations --------------------------------------------------------------


def test_rejected_recommendations():
    event_service, outcome_service, audit_service, comparison_service, feedback_service, policy_service = _stack()
    _feed(
        "task-1",
        event_service,
        outcome_service,
        audit_service,
        comparison_service,
        feedback_service,
        recommended_action=RECOVERY_ACTION_REFRESH_CONTEXT,
        executed_action=RECOVERY_ACTION_MARK_UNRECOVERABLE,
    )

    result = policy_service.analyze()

    assert result.recommendations_followed == 0
    assert result.recommendations_changed == 1
    assert result.decisions_evaluated == 1


# --- unknown outcomes --------------------------------------------------------------


def test_unknown_outcomes_no_corresponding_recovery():
    event_service, outcome_service, audit_service, comparison_service, feedback_service, policy_service = _stack()
    _feed(
        "task-1", event_service, outcome_service, audit_service, comparison_service, feedback_service, no_recovery=True
    )

    result = policy_service.analyze()

    assert result.decisions_evaluated == 1
    assert result.unknown_outcomes == 1
    assert result.effective_decisions == 0
    assert result.ineffective_decisions == 0
    assert result.effectiveness_rate is None
    # never acted on: neither followed nor changed
    assert result.recommendations_followed == 0
    assert result.recommendations_changed == 0


def test_unknown_outcomes_insufficient_evidence():
    event_service, outcome_service, audit_service, comparison_service, feedback_service, policy_service = _stack(
        with_classifier=False
    )
    _feed("task-1", event_service, outcome_service, audit_service, comparison_service, feedback_service)

    result = policy_service.analyze()

    assert result.unknown_outcomes == 1
    assert result.recommendations_followed == 1  # was followed, just effectiveness is unknown
    assert result.effectiveness_rate is None


# --- action-level effectiveness --------------------------------------------------------------


def test_action_level_effectiveness():
    event_service, outcome_service, audit_service, comparison_service, feedback_service, policy_service = _stack()
    _feed(
        "task-1",
        event_service,
        outcome_service,
        audit_service,
        comparison_service,
        feedback_service,
        recommended_action=RECOVERY_ACTION_REFRESH_CONTEXT,
        effective=True,
        success=True,
    )
    _feed(
        "task-2",
        event_service,
        outcome_service,
        audit_service,
        comparison_service,
        feedback_service,
        recommended_action=RECOVERY_ACTION_RETRY,
        executed_action=RECOVERY_ACTION_RETRY,
        effective=False,
        success=False,
    )

    result = policy_service.analyze()

    assert set(result.effectiveness_by_action.keys()) == {RECOVERY_ACTION_REFRESH_CONTEXT, RECOVERY_ACTION_RETRY}
    context_breakdown = result.effectiveness_by_action[RECOVERY_ACTION_REFRESH_CONTEXT]
    retry_breakdown = result.effectiveness_by_action[RECOVERY_ACTION_RETRY]
    assert context_breakdown.effective_count == 1
    assert context_breakdown.effectiveness_rate == 1.0
    assert retry_breakdown.ineffective_count == 1
    assert retry_breakdown.effectiveness_rate == 0.0
    # a poor action's own stats never leak into an unrelated action's breakdown
    assert context_breakdown.ineffective_count == 0


# --- policy-level grouping where supported --------------------------------------------------------------


def test_policy_level_grouping_with_classifier():
    event_service, outcome_service, audit_service, comparison_service, feedback_service, policy_service = _stack()
    feedback = _feed("task-1", event_service, outcome_service, audit_service, comparison_service, feedback_service)

    result = policy_service.analyze()

    # task-1's single illegal-claim failure classifies under some category; whatever
    # it is, it should show up as exactly one identifiable policy group.
    assert len(result.effectiveness_by_policy) == 1
    (category, breakdown), = result.effectiveness_by_policy.items()
    assert breakdown.decisions_evaluated == 1
    assert feedback.decision_id in breakdown.supporting_decision_ids


def test_policy_level_grouping_without_classifier_is_empty():
    event_service, outcome_service, audit_service, comparison_service, feedback_service, policy_service = _stack(
        with_classifier=False
    )
    _feed("task-1", event_service, outcome_service, audit_service, comparison_service, feedback_service)

    result = policy_service.analyze()

    assert result.effectiveness_by_policy == {}


def test_policy_id_filter_without_classifier_yields_empty_result():
    event_service, outcome_service, audit_service, comparison_service, feedback_service, policy_service = _stack(
        with_classifier=False
    )
    _feed("task-1", event_service, outcome_service, audit_service, comparison_service, feedback_service)

    result = policy_service.analyze(policy_id="execution")

    assert result.decisions_evaluated == 0


def test_policy_id_filter_with_classifier_matches_category():
    event_service, outcome_service, audit_service, comparison_service, feedback_service, policy_service = _stack()
    feedback = _feed("task-1", event_service, outcome_service, audit_service, comparison_service, feedback_service)
    unfiltered = policy_service.analyze()
    (category,) = unfiltered.effectiveness_by_policy.keys()

    matching = policy_service.analyze(policy_id=category)
    non_matching = policy_service.analyze(policy_id="definitely-not-a-real-category")

    assert matching.decisions_evaluated == 1
    assert feedback.decision_id in matching.supporting_decision_ids
    assert non_matching.decisions_evaluated == 0


# --- empty dataset --------------------------------------------------------------


def test_empty_dataset():
    *_, policy_service = _stack()

    result = policy_service.analyze()

    assert result.decisions_evaluated == 0
    assert result.recommendations_followed == 0
    assert result.recommendations_changed == 0
    assert result.effective_decisions == 0
    assert result.ineffective_decisions == 0
    assert result.unknown_outcomes == 0
    assert result.effectiveness_rate is None
    assert result.effectiveness_by_action == {}
    assert result.effectiveness_by_policy == {}
    assert result.supporting_decision_ids == ()
    assert result.supporting_recovery_ids == ()


# --- task/policy filtering --------------------------------------------------------------


def test_task_id_filtering():
    event_service, outcome_service, audit_service, comparison_service, feedback_service, policy_service = _stack()
    _feed("task-1", event_service, outcome_service, audit_service, comparison_service, feedback_service, effective=True, success=True)
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

    task_1_result = policy_service.analyze(task_id="task-1")
    task_2_result = policy_service.analyze(task_id="task-2")
    all_result = policy_service.analyze()

    assert task_1_result.decisions_evaluated == 1
    assert task_1_result.effective_decisions == 1
    assert task_2_result.decisions_evaluated == 1
    assert task_2_result.ineffective_decisions == 1
    assert all_result.decisions_evaluated == 2


def test_task_id_filter_rejects_blank_string():
    *_, policy_service = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryPolicyEffectivenessError):
        policy_service.analyze(task_id="")


def test_policy_id_filter_rejects_blank_string():
    *_, policy_service = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryPolicyEffectivenessError):
        policy_service.analyze(policy_id="")


# --- deterministic repeated analysis --------------------------------------------------------------


def test_deterministic_repeated_analysis():
    event_service, outcome_service, audit_service, comparison_service, feedback_service, policy_service = _stack()
    _feed("task-1", event_service, outcome_service, audit_service, comparison_service, feedback_service)
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

    first = policy_service.analyze()
    second = policy_service.analyze()

    assert first == second


def test_repeated_decision_evaluation_is_deduplicated_to_latest():
    event_service, outcome_service, audit_service, comparison_service, feedback_service, policy_service = _stack()
    failing = _illegal_failure(event_service)
    audit = audit_service.record("task-1", _recommendation(failure_event_id=failing.event_id))

    # First evaluated with no corresponding recovery at all (unknown).
    comparison_1 = comparison_service.compare("task-1", decision_id=audit.decision_id)
    feedback_service.record("task-1", comparison_1)

    # A recovery attempt appears afterward; re-evaluating the SAME decision
    # now yields real, effective evidence -- a genuinely new, distinct
    # feedback record for the same decision_id.
    outcome_service.record("task-1", _outcome_result(source_failure_event_id=failing.event_id, success=True))
    comparison_2 = comparison_service.compare("task-1", decision_id=audit.decision_id)
    feedback_service.record("task-1", comparison_2)

    assert len(feedback_service.list("task-1")) == 2

    result = policy_service.analyze()

    assert result.decisions_evaluated == 1
    assert result.effective_decisions == 1
    assert result.unknown_outcomes == 0
