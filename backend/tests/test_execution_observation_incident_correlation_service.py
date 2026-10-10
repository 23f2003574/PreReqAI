import pytest

from backend.session import (
    ExecutionObservationCorrelationRuleError as Error,
    ExecutionObservationCorrelationRule,
    ExecutionObservationEvent,
    ExecutionObservationEventService,
    ExecutionObservationIncidentCorrelationService,
    ExecutionObservationIncidentService,
)


def _rule(event_types=("ERROR",), severity="HIGH", enabled=True, rule_id=None):
    kwargs = dict(event_types=event_types, severity=severity, enabled=enabled)

    if rule_id is not None:
        kwargs["rule_id"] = rule_id

    return ExecutionObservationCorrelationRule(**kwargs)


def _services():
    return ExecutionObservationEventService(), ExecutionObservationIncidentService()


class TestExecutionObservationIncidentCorrelationService:
    def test_register_rule(self):
        event_service, incident_service = _services()
        correlation_service = ExecutionObservationIncidentCorrelationService(event_service, incident_service)
        rule = _rule()

        registered = correlation_service.register(rule)

        assert registered == rule
        assert correlation_service.rules() == [rule]

    def test_matching_events(self):
        event_service, incident_service = _services()
        correlation_service = ExecutionObservationIncidentCorrelationService(event_service, incident_service)
        rule = _rule(event_types=("ERROR",))
        correlation_service.register(rule)

        first = event_service.record(ExecutionObservationEvent(session_id="session-1", event_type="ERROR"))
        second = event_service.record(ExecutionObservationEvent(session_id="session-1", event_type="ERROR"))

        incidents = correlation_service.evaluate("session-1")

        assert len(incidents) == 1
        assert incidents[0].event_ids == (first.event_id, second.event_id)
        assert incidents[0].severity == "HIGH"

    def test_non_matching_events(self):
        event_service, incident_service = _services()
        correlation_service = ExecutionObservationIncidentCorrelationService(event_service, incident_service)
        correlation_service.register(_rule(event_types=("ERROR",)))

        event_service.record(ExecutionObservationEvent(session_id="session-1", event_type="INFO"))

        incidents = correlation_service.evaluate("session-1")

        assert incidents == []
        assert incident_service.active("session-1") == []

    def test_disabled_rule(self):
        event_service, incident_service = _services()
        correlation_service = ExecutionObservationIncidentCorrelationService(event_service, incident_service)
        rule = _rule(event_types=("ERROR",), enabled=False)
        correlation_service.register(rule)

        event = ExecutionObservationEvent(session_id="session-1", event_type="ERROR")
        event_service.record(event)

        assert correlation_service.matches(rule, event) is False
        assert correlation_service.evaluate("session-1") == []

    def test_multiple_rules(self):
        event_service, incident_service = _services()
        correlation_service = ExecutionObservationIncidentCorrelationService(event_service, incident_service)
        error_rule = _rule(rule_id="rule-error", event_types=("ERROR",), severity="HIGH")
        timeout_rule = _rule(rule_id="rule-timeout", event_types=("TIMEOUT",), severity="LOW")
        correlation_service.register(error_rule)
        correlation_service.register(timeout_rule)

        error_event = event_service.record(ExecutionObservationEvent(session_id="session-1", event_type="ERROR"))
        timeout_event = event_service.record(
            ExecutionObservationEvent(session_id="session-1", event_type="TIMEOUT")
        )

        incidents = correlation_service.evaluate("session-1")

        assert len(incidents) == 2
        assert incidents[0].event_ids == (error_event.event_id,)
        assert incidents[0].severity == "HIGH"
        assert incidents[1].event_ids == (timeout_event.event_id,)
        assert incidents[1].severity == "LOW"

    def test_ordering(self):
        event_service, incident_service = _services()
        correlation_service = ExecutionObservationIncidentCorrelationService(event_service, incident_service)
        correlation_service.register(_rule(event_types=("ERROR",)))

        first = event_service.record(ExecutionObservationEvent(session_id="session-1", event_type="ERROR"))

        first_evaluation = correlation_service.evaluate("session-1")
        assert first_evaluation[0].event_ids == (first.event_id,)

        second = event_service.record(ExecutionObservationEvent(session_id="session-1", event_type="ERROR"))

        # A later evaluate() extends the same still-active incident, preserving chronological order.
        second_evaluation = correlation_service.evaluate("session-1")

        assert len(second_evaluation) == 1
        assert second_evaluation[0].incident_id == first_evaluation[0].incident_id
        assert second_evaluation[0].event_ids == (first.event_id, second.event_id)
