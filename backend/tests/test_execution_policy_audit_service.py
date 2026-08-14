from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.session import (
    ExecutionPolicyAuditError as Error,
    ExecutionPolicyAuditEvent,
    ExecutionPolicyAuditService,
)


def _event(
    event_id="event-1",
    session_id="session-1",
    policy_ids=("policy-1",),
    event_type="enforcement",
    decision="allowed",
    timestamp=None,
    metadata=None,
):
    return ExecutionPolicyAuditEvent(
        event_id=event_id,
        session_id=session_id,
        policy_ids=policy_ids,
        event_type=event_type,
        decision=decision,
        timestamp=timestamp or datetime.now(timezone.utc),
        metadata=metadata or {},
    )


class TestExecutionPolicyAuditService:
    def test_record_event(self):
        service = ExecutionPolicyAuditService()
        event = _event()

        recorded = service.record(event)

        assert recorded is event

    def test_record_duplicate_event_id_is_rejected(self):
        service = ExecutionPolicyAuditService()
        service.record(_event())

        with pytest.raises(Error):
            service.record(_event())

    def test_session_history(self):
        service = ExecutionPolicyAuditService()
        now = datetime.now(timezone.utc)

        second = _event(event_id="event-2", event_type="conflict", decision="detected", timestamp=now)
        first = _event(event_id="event-1", event_type="evaluation", decision="allowed", timestamp=now - timedelta(seconds=5))

        service.record(second)
        service.record(first)

        assert service.history("session-1") == [first, second]

    def test_policy_history(self):
        service = ExecutionPolicyAuditService()
        matching = _event(event_id="event-1", policy_ids=("policy-1", "policy-2"))
        other = _event(event_id="event-2", policy_ids=("policy-2",))
        unrelated = _event(event_id="event-3", policy_ids=("policy-3",))

        service.record(matching)
        service.record(other)
        service.record(unrelated)

        assert service.policy_history("policy-2") == [matching, other]
        assert service.policy_history("policy-3") == [unrelated]

    def test_latest_event(self):
        service = ExecutionPolicyAuditService()
        now = datetime.now(timezone.utc)

        older = _event(event_id="event-1", timestamp=now - timedelta(seconds=5))
        newer = _event(event_id="event-2", timestamp=now)

        service.record(older)
        service.record(newer)

        assert service.latest("session-1") == newer

    def test_latest_with_no_events_is_an_error(self):
        service = ExecutionPolicyAuditService()

        with pytest.raises(Error):
            service.latest("unknown-session")

    def test_purge(self):
        service = ExecutionPolicyAuditService()
        now = datetime.now(timezone.utc)

        old = _event(event_id="event-1", policy_ids=("policy-1",), timestamp=now - timedelta(days=1))
        recent = _event(event_id="event-2", policy_ids=("policy-1",), timestamp=now)

        service.record(old)
        service.record(recent)

        purged = service.purge(now - timedelta(hours=1))

        assert purged == [old]
        assert service.history("session-1") == [recent]
        assert service.policy_history("policy-1") == [recent]

    def test_purge_requires_a_cutoff(self):
        service = ExecutionPolicyAuditService()

        with pytest.raises(Error):
            service.purge(None)

    def test_sensitive_value_exclusion(self):
        with pytest.raises(Error):
            _event(metadata={"api_secret": "shhh"})

        with pytest.raises(Error):
            _event(metadata={"session_token": "abc123"})

        allowed = _event(metadata={"rule": "delete", "outcome": "denied"})
        assert dict(allowed.metadata) == {"rule": "delete", "outcome": "denied"}
