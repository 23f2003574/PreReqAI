"""Tests for LLMAgentTaskRecoveryExecutionDecisionLifecycleFacade's
structured event trail, emitted through the repository's existing
append-only event stream (backend.agent_task_events.LLMAgentTaskEventService)
-- not a new observability framework.
"""

from backend.agent_task_events import LLMAgentTaskEventService

from backend.agent_task_recovery_execution_precondition_snapshots import (
    DECISION_RESOLVED,
    IMPACT_ANALYZED,
    LIFECYCLE_BLOCKED,
    LIFECYCLE_FACADE_COMPLETED,
    LIFECYCLE_FACADE_FAILED,
    LIFECYCLE_STARTED,
    LIFECYCLE_VERIFIED,
    RECONCILIATION_STARTED,
    REMEDIATION_STARTED,
    STALE_ARTIFACTS_DETECTED,
    LLMAgentTaskRecoveryExecutionDecisionLifecycleFacade,
    LLMAgentTaskRecoveryExecutionDecisionSupersessionValidationService,
)

from backend.tests.test_llm_agent_task_recovery_execution_decision_impact_invalidation_lifecycle_reconciliation import (
    TASK_ID,
    _Recon,
)


def _facade(recon, events):
    supersession_validation = LLMAgentTaskRecoveryExecutionDecisionSupersessionValidationService(
        decision_store=recon.f.decision_store,
    )
    return LLMAgentTaskRecoveryExecutionDecisionLifecycleFacade(
        supersession_validation_service=supersession_validation,
        lifecycle_service=recon.lifecycle,
        lifecycle_result_service=recon.results,
        lifecycle_verification_service=recon.verifier,
        reconciliation_service=recon.service,
        event_service=events,
    )


def _event_types(events):
    return [event.event_type for event in events.get(TASK_ID)]


def test_successful_lifecycle_emits_the_full_trail_ending_in_lifecycle_completed():
    """A single-decision task has nothing stale and nothing left
    blocking -- CLEAN, verified, and reported as lifecycle_completed."""
    events = LLMAgentTaskEventService()
    recon = _Recon(resolution_chain=("d1",))
    facade = _facade(recon, events)

    result = facade.evaluate(TASK_ID)

    assert _event_types(events) == [
        LIFECYCLE_STARTED, REMEDIATION_STARTED, DECISION_RESOLVED, IMPACT_ANALYZED,
        LIFECYCLE_VERIFIED, LIFECYCLE_FACADE_COMPLETED,
    ]
    assert result.overall_status == "clean"
    assert result.blocking_conditions == ()

    terminal = events.get(TASK_ID, event_type=LIFECYCLE_FACADE_COMPLETED)[0]
    assert terminal.payload == {
        "lifecycle_result_id": recon.results.latest(TASK_ID).result_id,
        "overall_status": "clean",
        "verification_status": "valid",
        "blocking_condition_count": 0,
    }


def test_blocked_lifecycle_emits_stale_artifacts_detected_and_lifecycle_blocked():
    """The default fixture's d1 -> d2 transition leaves real artifacts
    blocking -- reported as lifecycle_blocked, never completed/failed."""
    events = LLMAgentTaskEventService()
    recon = _Recon()
    facade = _facade(recon, events)

    result = facade.evaluate(TASK_ID)

    assert _event_types(events) == [
        LIFECYCLE_STARTED, REMEDIATION_STARTED, DECISION_RESOLVED, IMPACT_ANALYZED,
        STALE_ARTIFACTS_DETECTED, LIFECYCLE_VERIFIED, LIFECYCLE_BLOCKED,
    ]
    assert result.blocking_conditions != ()

    terminal = events.get(TASK_ID, event_type=LIFECYCLE_BLOCKED)[0]
    assert terminal.payload["blocking_condition_count"] == len(result.blocking_conditions)
    assert terminal.operation_id == result.remediation_operation_id


def test_failed_unresolved_lifecycle_emits_lifecycle_failed_and_skips_decision_events():
    """No authoritative decision can be established -- decision_resolved/
    impact_analyzed never fire (nothing was actually resolved or
    analyzed), and the trail ends in lifecycle_failed."""
    events = LLMAgentTaskEventService()
    recon = _Recon(resolution_chain=())
    facade = _facade(recon, events)

    result = facade.evaluate(TASK_ID)

    assert _event_types(events) == [
        LIFECYCLE_STARTED, REMEDIATION_STARTED, LIFECYCLE_VERIFIED, LIFECYCLE_FACADE_FAILED,
    ]
    assert result.overall_status == "unresolved"

    terminal = events.get(TASK_ID, event_type=LIFECYCLE_FACADE_FAILED)[0]
    assert terminal.payload["overall_status"] == "unresolved"
    assert terminal.payload["verification_status"] == "invalid"


def test_all_events_from_one_evaluate_call_share_one_correlation_id():
    events = LLMAgentTaskEventService()
    recon = _Recon(resolution_chain=("d1",))
    facade = _facade(recon, events)

    facade.evaluate(TASK_ID)

    recorded = events.get(TASK_ID)
    correlation_ids = {event.correlation_id for event in recorded}
    assert len(correlation_ids) == 1
    assert all(event.correlation_id for event in recorded)
    assert all(event.task_id == TASK_ID for event in recorded)


def test_second_call_emits_reconciliation_started_referencing_the_previous_result():
    events = LLMAgentTaskEventService()
    recon = _Recon(resolution_chain=("d1",))
    facade = _facade(recon, events)

    facade.evaluate(TASK_ID)
    first_correlation_ids = {event.correlation_id for event in events.get(TASK_ID)}
    previous_result_id = recon.results.latest(TASK_ID).result_id

    facade.evaluate(TASK_ID)

    second_events = [
        event for event in events.get(TASK_ID) if event.correlation_id not in first_correlation_ids
    ]
    assert second_events[0].event_type == LIFECYCLE_STARTED
    assert second_events[1].event_type == RECONCILIATION_STARTED
    assert second_events[1].payload == {"previous_lifecycle_result_id": previous_result_id}


def test_event_payloads_never_carry_raw_decision_or_snapshot_content():
    """Payloads are ids/counts/statuses only -- never a copy of a
    decision, snapshot, or authorization record."""
    events = LLMAgentTaskEventService()
    recon = _Recon()
    facade = _facade(recon, events)

    facade.evaluate(TASK_ID)

    allowed_keys = {
        "authoritative_decision_id", "affected_artifact_count", "stale_artifact_count",
        "previous_lifecycle_result_id", "lifecycle_result_id", "overall_status",
        "verification_status", "blocking_condition_count",
    }
    for event in events.get(TASK_ID):
        if event.payload is not None:
            assert set(event.payload.keys()) <= allowed_keys


def test_facade_defaults_its_own_event_service_when_none_given():
    """Backward compatible: event_service is optional, matching the
    "wire a dedicated store when none is given" default this package's
    other metrics/event consumers already use."""
    recon = _Recon(resolution_chain=("d1",))
    supersession_validation = LLMAgentTaskRecoveryExecutionDecisionSupersessionValidationService(
        decision_store=recon.f.decision_store,
    )
    facade = LLMAgentTaskRecoveryExecutionDecisionLifecycleFacade(
        supersession_validation_service=supersession_validation,
        lifecycle_service=recon.lifecycle,
        lifecycle_result_service=recon.results,
        lifecycle_verification_service=recon.verifier,
        reconciliation_service=recon.service,
    )

    result = facade.evaluate(TASK_ID)

    assert result.overall_status == "clean"
