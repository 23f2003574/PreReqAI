import pytest

from backend.session import (
    ExecutionObservationIncidentError as Error,
    ExecutionObservationIncidentService,
)


class TestExecutionObservationIncidentService:
    def test_open_incident(self):
        incident_service = ExecutionObservationIncidentService()

        incident = incident_service.open("session-1", ["error-1", "alert-1"], severity="HIGH")

        assert incident.session_id == "session-1"
        assert incident.severity == "HIGH"
        assert incident.event_ids == ("error-1", "alert-1")
        assert incident.status == "ACTIVE"
        assert incident.resolved_at is None

    def test_add_events(self):
        incident_service = ExecutionObservationIncidentService()
        incident = incident_service.open("session-1", ["error-1"])

        updated = incident_service.add(incident.incident_id, "alert-1")

        assert updated.event_ids == ("error-1", "alert-1")

        with pytest.raises(Error):
            incident_service.add(incident.incident_id, "alert-1")

    def test_active_lookup(self):
        incident_service = ExecutionObservationIncidentService()
        first = incident_service.open("session-1", ["error-1"])
        second = incident_service.open("session-1", ["error-2"])

        assert incident_service.active("session-1") == [first, second]

        incident_service.resolve(first.incident_id)

        assert incident_service.active("session-1") == [second]

    def test_resolve_incident(self):
        incident_service = ExecutionObservationIncidentService()
        incident = incident_service.open("session-1", ["error-1"])

        resolved = incident_service.resolve(incident.incident_id)

        assert resolved.status == "RESOLVED"
        assert resolved.resolved_at is not None

        with pytest.raises(Error):
            incident_service.resolve("unknown-incident")

    def test_reject_closed_incident_update(self):
        incident_service = ExecutionObservationIncidentService()
        incident = incident_service.open("session-1", ["error-1"])
        incident_service.resolve(incident.incident_id)

        with pytest.raises(Error):
            incident_service.add(incident.incident_id, "alert-1")

        with pytest.raises(Error):
            incident_service.resolve(incident.incident_id)

    def test_event_ordering(self):
        incident_service = ExecutionObservationIncidentService()
        incident = incident_service.open("session-1", ["error-1", "error-2"])
        incident = incident_service.add(incident.incident_id, "alert-1")
        incident = incident_service.add(incident.incident_id, "transition-1")

        assert incident.event_ids == ("error-1", "error-2", "alert-1", "transition-1")

        history = incident_service.history("session-1")
        assert history == [incident]
