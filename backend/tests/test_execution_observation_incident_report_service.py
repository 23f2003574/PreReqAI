import pytest

from backend.session import (
    ExecutionObservationIncidentLifecycleService,
    ExecutionObservationIncidentReportError as Error,
    ExecutionObservationIncidentReportService,
)


class _FakeIncident:
    def __init__(self, incident_id, severity, event_ids):
        self.incident_id = incident_id
        self.severity = severity
        self.event_ids = tuple(event_ids)


class _FakeIncidentService:
    def __init__(self):
        self._incidents = {}

    def add(self, incident):
        self._incidents[incident.incident_id] = incident

    def get(self, incident_id):
        incident = self._incidents.get(incident_id)

        if incident is None:
            raise ValueError(f"unknown incident {incident_id!r}")

        return incident


def _services():
    return _FakeIncidentService(), ExecutionObservationIncidentLifecycleService()


class TestExecutionObservationIncidentReportService:
    def test_generate_report(self):
        incident_service, lifecycle_service = _services()
        report_service = ExecutionObservationIncidentReportService(incident_service, lifecycle_service)
        incident_service.add(_FakeIncident("incident-1", "HIGH", ["event-1", "event-2"]))
        lifecycle_service.acknowledge("incident-1", "operator-1")
        lifecycle_service.escalate("incident-1", "operator-1")

        report = report_service.generate("incident-1")

        assert report.incident_id == "incident-1"
        assert report.severity == "HIGH"
        assert report.events == ("event-1", "event-2")
        assert [transition.to_status for transition in report.transitions] == ["ACKNOWLEDGED", "ESCALATED"]

    def test_retrieve_report(self):
        incident_service, lifecycle_service = _services()
        report_service = ExecutionObservationIncidentReportService(incident_service, lifecycle_service)
        incident_service.add(_FakeIncident("incident-1", "LOW", ["event-1"]))

        report = report_service.generate("incident-1")

        assert report_service.get(report.report_id) == report

        with pytest.raises(Error):
            report_service.get("unknown-report")

    def test_complete_history(self):
        incident_service, lifecycle_service = _services()
        report_service = ExecutionObservationIncidentReportService(incident_service, lifecycle_service)
        incident_service.add(_FakeIncident("incident-1", "LOW", ["event-1"]))

        first = report_service.generate("incident-1")
        lifecycle_service.acknowledge("incident-1", "operator-1")
        second = report_service.generate("incident-1")

        history = report_service.history("incident-1")

        assert history == [first, second]
        assert history[0].transitions == ()
        assert len(history[1].transitions) == 1

    def test_deterministic_output(self):
        incident_service, lifecycle_service = _services()
        report_service = ExecutionObservationIncidentReportService(incident_service, lifecycle_service)
        incident_service.add(_FakeIncident("incident-1", "LOW", ["event-1", "event-2"]))
        lifecycle_service.acknowledge("incident-1", "operator-1")

        first = report_service.generate("incident-1")
        second = report_service.generate("incident-1")

        assert first.events == second.events
        assert first.transitions == second.transitions
        assert first.severity == second.severity
        assert first.report_id != second.report_id

    def test_report_comparison(self):
        incident_service, lifecycle_service = _services()
        report_service = ExecutionObservationIncidentReportService(incident_service, lifecycle_service)
        incident_service.add(_FakeIncident("incident-1", "LOW", ["event-1"]))

        report_a = report_service.generate("incident-1")
        lifecycle_service.acknowledge("incident-1", "operator-1")
        escalation = lifecycle_service.escalate("incident-1", "operator-1")
        report_b = report_service.generate("incident-1")

        diff = report_service.compare(report_a, report_b)

        assert diff["severity_changed"] is False
        assert diff["new_events"] == ()
        assert diff["new_transitions"] == (lifecycle_service.history("incident-1")[0], escalation)

        with pytest.raises(Error):
            report_service.compare(report_a, "not-a-report")

    def test_unknown_incident_rejection(self):
        incident_service, lifecycle_service = _services()
        report_service = ExecutionObservationIncidentReportService(incident_service, lifecycle_service)

        with pytest.raises(Error):
            report_service.generate("unknown-incident")
