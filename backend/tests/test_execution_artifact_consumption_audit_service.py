from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.session import (
    ExecutionArtifactConsumptionAuditError as Error,
    ExecutionArtifactConsumptionAuditEvent,
    ExecutionArtifactConsumptionAuditService,
)


def _event(
    consumption_id="consumption-1",
    artifact_id="artifact-1",
    version=1,
    event_type="CONSUMED",
    event_id=None,
    recorded_at=None,
):
    kwargs = dict(
        consumption_id=consumption_id,
        artifact_id=artifact_id,
        version=version,
        event_type=event_type,
    )

    if event_id is not None:
        kwargs["event_id"] = event_id

    if recorded_at is not None:
        kwargs["recorded_at"] = recorded_at

    return ExecutionArtifactConsumptionAuditEvent(**kwargs)


class TestExecutionArtifactConsumptionAuditService:
    def test_record_event(self):
        audit_service = ExecutionArtifactConsumptionAuditService()
        event = _event()

        recorded = audit_service.record(event)

        assert recorded == event
        assert audit_service.history("consumption-1") == [event]

    def test_consumption_history(self):
        audit_service = ExecutionArtifactConsumptionAuditService()
        base = datetime.now(timezone.utc)
        first = _event(event_id="event-1", recorded_at=base)
        second = _event(event_id="event-2", recorded_at=base + timedelta(seconds=1))
        # Record out of chronological order to prove history() sorts by recorded_at.
        audit_service.record(second)
        audit_service.record(first)

        history = audit_service.history("consumption-1")

        assert [event.event_id for event in history] == ["event-1", "event-2"]

    def test_artifact_history(self):
        audit_service = ExecutionArtifactConsumptionAuditService()
        base = datetime.now(timezone.utc)
        first = _event(event_id="event-1", consumption_id="consumption-1", recorded_at=base)
        second = _event(event_id="event-2", consumption_id="consumption-2", recorded_at=base + timedelta(seconds=1))
        other_artifact = _event(event_id="event-3", artifact_id="artifact-2", recorded_at=base)
        audit_service.record(first)
        audit_service.record(second)
        audit_service.record(other_artifact)

        artifact_history = audit_service.artifact_history("artifact-1")

        assert [event.event_id for event in artifact_history] == ["event-1", "event-2"]

    def test_latest_event(self):
        audit_service = ExecutionArtifactConsumptionAuditService()
        base = datetime.now(timezone.utc)
        first = _event(event_id="event-1", recorded_at=base)
        second = _event(event_id="event-2", recorded_at=base + timedelta(seconds=1))
        audit_service.record(first)
        audit_service.record(second)

        assert audit_service.latest("consumption-1") == second

        with pytest.raises(Error):
            audit_service.latest("unknown-consumption")

    def test_purge_old_events(self):
        audit_service = ExecutionArtifactConsumptionAuditService()
        base = datetime.now(timezone.utc)
        old_event = _event(event_id="event-old", recorded_at=base - timedelta(days=10))
        recent_event = _event(event_id="event-recent", recorded_at=base)
        audit_service.record(old_event)
        audit_service.record(recent_event)

        purged = audit_service.purge(base - timedelta(days=1))

        assert purged == [old_event]
        assert audit_service.history("consumption-1") == [recent_event]

        with pytest.raises(Error):
            audit_service.purge("not-a-datetime")

    def test_duplicate_event_rejection(self):
        audit_service = ExecutionArtifactConsumptionAuditService()
        event = _event(event_id="event-1")
        audit_service.record(event)

        duplicate = _event(event_id="event-1", version=2)

        with pytest.raises(Error):
            audit_service.record(duplicate)

    def test_rejects_invalid_event(self):
        audit_service = ExecutionArtifactConsumptionAuditService()

        with pytest.raises(Error):
            audit_service.record("not-an-event")
