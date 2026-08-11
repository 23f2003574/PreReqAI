import pytest

from backend.session import (
    ExecutionObservationIncidentTransitionError as Error,
    ExecutionObservationIncidentLifecycleService,
)


class TestExecutionObservationIncidentLifecycleService:
    def test_acknowledge(self):
        lifecycle_service = ExecutionObservationIncidentLifecycleService()

        assert lifecycle_service.status("incident-1") == "OPEN"

        transition = lifecycle_service.acknowledge("incident-1", "operator-1")

        assert transition.from_status == "OPEN"
        assert transition.to_status == "ACKNOWLEDGED"
        assert transition.actor == "operator-1"
        assert lifecycle_service.status("incident-1") == "ACKNOWLEDGED"

    def test_escalate(self):
        lifecycle_service = ExecutionObservationIncidentLifecycleService()
        lifecycle_service.acknowledge("incident-1", "operator-1")

        transition = lifecycle_service.escalate("incident-1", "operator-2")

        assert transition.from_status == "ACKNOWLEDGED"
        assert transition.to_status == "ESCALATED"
        assert lifecycle_service.status("incident-1") == "ESCALATED"

    def test_resolve(self):
        lifecycle_service = ExecutionObservationIncidentLifecycleService()
        lifecycle_service.acknowledge("incident-1", "operator-1")

        transition = lifecycle_service.resolve("incident-1", "operator-1")

        assert transition.from_status == "ACKNOWLEDGED"
        assert transition.to_status == "RESOLVED"
        assert lifecycle_service.status("incident-1") == "RESOLVED"

        # Resolution is also valid straight from ESCALATED.
        lifecycle_service.acknowledge("incident-2", "operator-1")
        lifecycle_service.escalate("incident-2", "operator-1")
        escalated_resolution = lifecycle_service.resolve("incident-2", "operator-1")

        assert escalated_resolution.from_status == "ESCALATED"
        assert escalated_resolution.to_status == "RESOLVED"

    def test_invalid_transition(self):
        lifecycle_service = ExecutionObservationIncidentLifecycleService()

        # Cannot escalate or resolve before acknowledging.
        with pytest.raises(Error):
            lifecycle_service.escalate("incident-1", "operator-1")

        with pytest.raises(Error):
            lifecycle_service.resolve("incident-1", "operator-1")

        lifecycle_service.acknowledge("incident-1", "operator-1")

        # Cannot acknowledge again once already ACKNOWLEDGED.
        with pytest.raises(Error):
            lifecycle_service.acknowledge("incident-1", "operator-1")

    def test_terminal_state_protection(self):
        lifecycle_service = ExecutionObservationIncidentLifecycleService()
        lifecycle_service.acknowledge("incident-1", "operator-1")
        lifecycle_service.resolve("incident-1", "operator-1")

        with pytest.raises(Error):
            lifecycle_service.acknowledge("incident-1", "operator-1")

        with pytest.raises(Error):
            lifecycle_service.escalate("incident-1", "operator-1")

        with pytest.raises(Error):
            lifecycle_service.resolve("incident-1", "operator-1")

    def test_transition_history(self):
        lifecycle_service = ExecutionObservationIncidentLifecycleService()

        assert lifecycle_service.history("incident-1") == []

        acknowledged = lifecycle_service.acknowledge("incident-1", "operator-1")
        escalated = lifecycle_service.escalate("incident-1", "operator-2")
        resolved = lifecycle_service.resolve("incident-1", "operator-3")

        assert lifecycle_service.history("incident-1") == [acknowledged, escalated, resolved]
