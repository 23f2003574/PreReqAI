from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuditError as Error,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuditEvent as AuditEvent,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuditService as AuditService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionTimeline as Timeline,
)


def _event(event_id, session_id="session-1", event_type="START", actor="worker-1", timestamp=None, metadata=None):
    return AuditEvent(
        event_id=event_id,
        session_id=session_id,
        event_type=event_type,
        actor=actor,
        timestamp=timestamp if timestamp is not None else datetime.now(timezone.utc),
        metadata=metadata if metadata is not None else {},
    )


class TestWorkspaceSessionAuditService:
    def test_record_event(self):
        service = AuditService()

        recorded = service.record(_event("event-1"))

        assert isinstance(recorded, AuditEvent)
        assert recorded.event_id == "event-1"

    def test_retrieve_timeline(self):
        service = AuditService()
        now = datetime.now(timezone.utc)

        # recorded out of chronological order
        service.record(_event("event-2", event_type="FINISH", timestamp=now + timedelta(seconds=1)))
        service.record(_event("event-1", event_type="START", timestamp=now))

        timeline = service.timeline("session-1")

        assert isinstance(timeline, Timeline)
        assert timeline.session_id == "session-1"
        assert [event.event_id for event in timeline.events] == ["event-1", "event-2"]

    def test_latest_event(self):
        service = AuditService()
        now = datetime.now(timezone.utc)

        assert service.latest("session-1") is None

        service.record(_event("event-1", event_type="START", timestamp=now))
        service.record(_event("event-2", event_type="FINISH", timestamp=now + timedelta(seconds=1)))

        assert service.latest("session-1").event_id == "event-2"

    def test_filter_by_type(self):
        service = AuditService()
        now = datetime.now(timezone.utc)

        service.record(_event("event-1", event_type="START", timestamp=now))
        service.record(_event("event-2", event_type="RESTORE", timestamp=now + timedelta(seconds=1)))
        service.record(_event("event-3", event_type="RESTORE", timestamp=now + timedelta(seconds=2)))

        restores = service.filter("session-1", "RESTORE")

        assert [event.event_id for event in restores] == ["event-2", "event-3"]

    def test_purge_expired_events(self):
        service = AuditService()
        now = datetime.now(timezone.utc)

        service.record(_event("event-1", timestamp=now - timedelta(days=2)))
        service.record(_event("event-2", timestamp=now))

        removed = service.purge(now - timedelta(days=1))

        assert removed == 1
        assert [event.event_id for event in service.timeline("session-1").events] == ["event-2"]

    def test_duplicate_event_rejection(self):
        service = AuditService()

        service.record(_event("event-1"))

        with pytest.raises(Error):
            service.record(_event("event-1"))

    def test_invalid_event_type_rejection(self):
        with pytest.raises(Error):
            _event("event-1", event_type="UNKNOWN_TYPE")

        service = AuditService()

        with pytest.raises(Error):
            service.filter("session-1", "UNKNOWN_TYPE")

    def test_blank_id_rejection(self):
        service = AuditService()

        with pytest.raises(Error):
            service.timeline("   ")

        with pytest.raises(Error):
            service.latest("   ")

        with pytest.raises(Error):
            service.filter("   ", "START")

        with pytest.raises(Error):
            service.record("not-an-event")

        with pytest.raises(Error):
            service.purge("not-a-datetime")
