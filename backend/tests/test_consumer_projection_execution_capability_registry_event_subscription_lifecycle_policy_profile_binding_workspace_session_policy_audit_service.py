from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionPolicy as Policy,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionPolicyService as PolicyService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyAuditError as Error,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyAuditEvent as AuditEvent,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyAuditService as AuditService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyDriftResult as DriftResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyVersionService as VersionService,
)


def _event(session_id="session-1", policy_id="policy-1", version=1, event_type="RESOLVED", timestamp=None):
    return AuditEvent(
        event_id="event-" + event_type.lower(),
        session_id=session_id,
        policy_id=policy_id,
        version=version,
        event_type=event_type,
        timestamp=timestamp or datetime.now(timezone.utc),
    )


def _build(actual_configuration):
    policy_service = PolicyService()
    policy_service.register(
        Policy(policy_id="policy-1", name="standard", max_runtime=3600, max_idle=300, allow_restore=True, enabled=True)
    )
    policy_service.assign("session-1", "policy-1")

    version_service = VersionService(policy_service, lambda pid: {"max_runtime": 3600, "max_idle": 300})
    version_service.publish("policy-1")

    audit_service = AuditService(version_service, actual_configuration_provider=lambda session_id: actual_configuration)

    return policy_service, version_service, audit_service


class TestWorkspaceSessionPolicyAuditService:
    def test_record_audit_event(self):
        _policy_service, _version_service, audit_service = _build({"max_runtime": 3600, "max_idle": 300})
        event = _event(event_type="RESOLVED")

        recorded = audit_service.record(event)

        assert recorded == event
        assert audit_service.history("session-1") == (event,)

        with pytest.raises(Error):
            audit_service.record("not-an-event")

    def test_detect_drift(self):
        _policy_service, _version_service, audit_service = _build({"max_runtime": 1800, "max_idle": 300})

        result = audit_service.detect_drift("session-1")

        assert isinstance(result, DriftResult)
        assert result.session_id == "session-1"
        assert result.compliant is False
        assert result.differences == ("max_runtime",)

        latest = audit_service.latest("session-1")
        assert latest.event_type == "DRIFT_DETECTED"

        with pytest.raises(Error):
            audit_service.detect_drift("   ")

    def test_retrieve_history(self):
        _policy_service, _version_service, audit_service = _build({"max_runtime": 3600, "max_idle": 300})

        older = _event(event_type="RESOLVED", timestamp=datetime.now(timezone.utc) - timedelta(seconds=10))
        newer = _event(event_type="COMPLIANT", timestamp=datetime.now(timezone.utc))

        audit_service.record(older)
        audit_service.record(newer)

        history = audit_service.history("session-1")

        assert history == (newer, older)
        assert audit_service.history("never-recorded") == ()

    def test_latest_event(self):
        _policy_service, _version_service, audit_service = _build({"max_runtime": 3600, "max_idle": 300})

        with pytest.raises(Error):
            audit_service.latest("session-1")

        first = _event(event_type="RESOLVED")
        second = _event(event_type="COMPLIANT")
        audit_service.record(first)
        audit_service.record(second)

        assert audit_service.latest("session-1") == second

    def test_purge_old_events(self):
        _policy_service, _version_service, audit_service = _build({"max_runtime": 3600, "max_idle": 300})

        now = datetime.now(timezone.utc)
        old_event = _event(event_type="RESOLVED", timestamp=now - timedelta(days=30))
        recent_event = _event(event_type="COMPLIANT", timestamp=now)

        audit_service.record(old_event)
        audit_service.record(recent_event)

        purged = audit_service.purge(now - timedelta(days=1))

        assert purged == 1
        assert audit_service.history("session-1") == (recent_event,)

        with pytest.raises(Error):
            audit_service.purge("not-a-datetime")

    def test_no_drift_for_compliant_session(self):
        _policy_service, _version_service, audit_service = _build({"max_runtime": 3600, "max_idle": 300})

        result = audit_service.detect_drift("session-1")

        assert result.compliant is True
        assert result.differences == ()

        latest = audit_service.latest("session-1")
        assert latest.event_type == "COMPLIANT"
