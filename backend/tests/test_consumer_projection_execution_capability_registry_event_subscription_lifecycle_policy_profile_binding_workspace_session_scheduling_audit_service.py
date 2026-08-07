from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingAuditEvent as Event,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingAuditError as Error,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingReplayResult as ReplayResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingAuditService as AuditService,
)


def _at(offset_seconds=0):
    return datetime.now(timezone.utc) + timedelta(seconds=offset_seconds)


def _event(event_id, schedule_id, event_type, timestamp=None, metadata=None):
    return Event(
        event_id=event_id,
        schedule_id=schedule_id,
        event_type=event_type,
        timestamp=timestamp if timestamp is not None else _at(),
        metadata=metadata if metadata is not None else {},
    )


class TestWorkspaceSessionSchedulingAuditService:
    def test_record_audit_event(self):
        service = AuditService()
        event = _event("event-1", "schedule-1", "scheduled")

        recorded = service.record(event)

        assert isinstance(recorded, Event)
        assert recorded.event_id == "event-1"

        with pytest.raises(Error):
            service.record(event)

    def test_retrieve_history(self):
        service = AuditService()
        service.record(_event("event-1", "schedule-1", "scheduled", timestamp=_at(-20)))
        service.record(_event("event-2", "schedule-1", "dispatched", timestamp=_at(-10)))
        service.record(_event("event-3", "schedule-2", "scheduled", timestamp=_at(-5)))

        history = service.history("schedule-1")

        assert [event.event_id for event in history] == ["event-2", "event-1"]

        with pytest.raises(Error):
            service.history("   ")

    def test_replay_scheduler_decisions(self):
        service = AuditService()
        earlier = _at(-20)
        later = _at(-10)

        # recorded out of chronological order on purpose
        service.record(_event("event-2", "schedule-1", "dispatched", timestamp=later))
        service.record(_event("event-1", "schedule-1", "scheduled", timestamp=earlier))

        result = service.replay("schedule-1")

        assert isinstance(result, ReplayResult)
        assert result.schedule_id == "schedule-1"
        assert result.replayed is True
        assert result.decision_trace == ("scheduled", "dispatched")

        empty = service.replay("schedule-without-events")
        assert empty.replayed is False
        assert empty.decision_trace == ()

    def test_latest_event_lookup(self):
        service = AuditService()
        service.record(_event("event-1", "schedule-1", "scheduled", timestamp=_at(-20)))
        service.record(_event("event-2", "schedule-1", "dispatched", timestamp=_at(-5)))

        latest = service.latest("schedule-1")

        assert latest.event_id == "event-2"

        with pytest.raises(Error):
            service.latest("unknown-schedule")

    def test_purge_expired_events(self):
        service = AuditService()
        old = _event("event-1", "schedule-1", "scheduled", timestamp=_at(-600))
        recent = _event("event-2", "schedule-1", "dispatched", timestamp=_at(0))
        service.record(old)
        service.record(recent)

        removed = service.purge(_at(-300))

        assert [event.event_id for event in removed] == ["event-1"]
        assert service.history("schedule-1") == (recent,)

        with pytest.raises(Error):
            service.purge(datetime.now())

    def test_replay_consistency(self):
        service = AuditService()
        service.record(_event("event-1", "schedule-1", "scheduled", timestamp=_at(-20)))
        service.record(_event("event-2", "schedule-1", "dispatched", timestamp=_at(-10)))
        service.record(_event("event-3", "schedule-1", "completed", timestamp=_at(-5)))

        first = service.replay("schedule-1")
        second = service.replay("schedule-1")

        assert first == second
        assert first.decision_trace == ("scheduled", "dispatched", "completed")
