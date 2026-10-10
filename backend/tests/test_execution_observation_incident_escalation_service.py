from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.session import (
    ExecutionObservationEscalationPolicyError as Error,
    ExecutionObservationEscalationPolicy,
    ExecutionObservationIncidentEscalationService,
    ExecutionObservationIncidentLifecycleService,
)


class _FakeIncident:
    def __init__(self, incident_id, severity, status="ACTIVE", opened_at=None):
        self.incident_id = incident_id
        self.severity = severity
        self.status = status
        self.opened_at = opened_at or datetime.now(timezone.utc)


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


def _policy(severity="HIGH", timeout_seconds=0, enabled=True, policy_id=None):
    kwargs = dict(severity=severity, timeout_seconds=timeout_seconds, enabled=enabled)

    if policy_id is not None:
        kwargs["policy_id"] = policy_id

    return ExecutionObservationEscalationPolicy(**kwargs)


def _services():
    return _FakeIncidentService(), ExecutionObservationIncidentLifecycleService()


class TestExecutionObservationIncidentEscalationService:
    def test_register_policy(self):
        incident_service, lifecycle_service = _services()
        escalation_service = ExecutionObservationIncidentEscalationService(incident_service, lifecycle_service)
        policy = _policy()

        registered = escalation_service.register(policy)

        assert registered == policy
        assert escalation_service.policies() == [policy]

    def test_severity_escalation(self):
        incident_service, lifecycle_service = _services()
        escalation_service = ExecutionObservationIncidentEscalationService(incident_service, lifecycle_service)
        escalation_service.register(_policy(severity="HIGH", timeout_seconds=0))

        incident_service.add(_FakeIncident("incident-1", severity="HIGH"))
        lifecycle_service.acknowledge("incident-1", "operator-1")

        transition = escalation_service.evaluate("incident-1")

        assert transition is not None
        assert transition.to_status == "ESCALATED"
        assert escalation_service.escalated("incident-1") is True

    def test_timeout_escalation(self):
        incident_service, lifecycle_service = _services()
        escalation_service = ExecutionObservationIncidentEscalationService(incident_service, lifecycle_service)
        escalation_service.register(_policy(severity="MEDIUM", timeout_seconds=60))

        long_running = _FakeIncident(
            "incident-old", severity="MEDIUM", opened_at=datetime.now(timezone.utc) - timedelta(seconds=120)
        )
        recent = _FakeIncident("incident-new", severity="MEDIUM")
        incident_service.add(long_running)
        incident_service.add(recent)
        lifecycle_service.acknowledge("incident-old", "operator-1")
        lifecycle_service.acknowledge("incident-new", "operator-1")

        assert escalation_service.evaluate("incident-old") is not None
        assert escalation_service.escalated("incident-old") is True

        assert escalation_service.evaluate("incident-new") is None
        assert escalation_service.escalated("incident-new") is False

    def test_disabled_policy(self):
        incident_service, lifecycle_service = _services()
        escalation_service = ExecutionObservationIncidentEscalationService(incident_service, lifecycle_service)
        escalation_service.register(_policy(severity="HIGH", timeout_seconds=0, enabled=False))

        incident_service.add(_FakeIncident("incident-1", severity="HIGH"))
        lifecycle_service.acknowledge("incident-1", "operator-1")

        assert escalation_service.evaluate("incident-1") is None
        assert escalation_service.escalated("incident-1") is False

    def test_already_escalated_incident(self):
        incident_service, lifecycle_service = _services()
        escalation_service = ExecutionObservationIncidentEscalationService(incident_service, lifecycle_service)
        escalation_service.register(_policy(severity="HIGH", timeout_seconds=0))

        incident_service.add(_FakeIncident("incident-1", severity="HIGH"))
        lifecycle_service.acknowledge("incident-1", "operator-1")
        lifecycle_service.escalate("incident-1", "operator-1")

        assert escalation_service.evaluate("incident-1") is None
        assert lifecycle_service.status("incident-1") == "ESCALATED"

    def test_policy_lookup(self):
        incident_service, lifecycle_service = _services()
        escalation_service = ExecutionObservationIncidentEscalationService(incident_service, lifecycle_service)
        high = escalation_service.register(_policy(severity="HIGH", timeout_seconds=0))
        medium = escalation_service.register(_policy(severity="MEDIUM", timeout_seconds=60))

        assert escalation_service.policies() == [high, medium]

        with pytest.raises(Error):
            escalation_service.register("not-a-policy")
