from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentAuditError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentAuditHistory,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentAuditRecord,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentAuditService,
)


def _record(audit_id, target_id, profile_id, operation, timestamp):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentAuditRecord(
        audit_id=audit_id,
        target_id=target_id,
        profile_id=profile_id,
        operation=operation,
        timestamp=timestamp,
    )


class TestProfileAssignmentAuditService:
    def test_record_audit_entry(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentAuditService()

        entry = _record("audit-1", "target-a", "development", "assign", datetime.now(timezone.utc))

        service.record(entry)

        assert service.list() == (entry,)

    def test_retrieve_target_history(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentAuditService()

        base = datetime.now(timezone.utc)
        first = _record("audit-1", "target-a", "development", "assign", base)
        second = _record("audit-2", "target-a", "staging", "assign", base + timedelta(seconds=5))
        other = _record("audit-3", "target-b", "development", "assign", base + timedelta(seconds=1))

        service.record(second)
        service.record(first)
        service.record(other)

        history = service.history("target-a")

        assert isinstance(history, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentAuditHistory)
        assert history.records == (first, second)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentAuditError):
            service.history("   ")

    def test_latest_entry(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentAuditService()

        base = datetime.now(timezone.utc)
        first = _record("audit-1", "target-a", "development", "assign", base)
        second = _record("audit-2", "target-a", None, "unassign", base + timedelta(seconds=5))

        service.record(first)
        service.record(second)

        assert service.latest("target-a") == second
        assert service.latest("target-unknown") is None

    def test_list_records(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentAuditService()

        base = datetime.now(timezone.utc)
        first = _record("audit-1", "target-a", "development", "assign", base + timedelta(seconds=10))
        second = _record("audit-2", "target-b", "staging", "assign", base)

        service.record(first)
        service.record(second)

        assert service.list() == (second, first)

    def test_purge_old_records(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentAuditService()

        base = datetime.now(timezone.utc)
        old = _record("audit-1", "target-a", "development", "assign", base - timedelta(days=2))
        recent = _record("audit-2", "target-a", "staging", "assign", base)

        service.record(old)
        service.record(recent)

        purged_count = service.purge(base - timedelta(days=1))

        assert purged_count == 1
        assert service.list() == (recent,)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentAuditError):
            service.purge(None)

    def test_reject_duplicate_ids(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentAuditService()

        first = _record("audit-1", "target-a", "development", "assign", datetime.now(timezone.utc))
        duplicate = _record("audit-1", "target-b", "staging", "assign", datetime.now(timezone.utc))

        service.record(first)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentAuditError):
            service.record(duplicate)

    def test_reject_invalid_records(self):
        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentAuditError):
            _record("   ", "target-a", "development", "assign", datetime.now(timezone.utc))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentAuditError):
            _record("audit-1", None, "development", "assign", datetime.now(timezone.utc))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentAuditError):
            _record("audit-1", "target-a", "development", "invalid", datetime.now(timezone.utc))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentAuditError):
            _record("audit-1", "target-a", None, "assign", datetime.now(timezone.utc))

        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentAuditService()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentAuditError):
            service.record(None)

    def test_immutable_audit_history(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentAuditService()

        entry = _record("audit-1", "target-a", "development", "assign", datetime.now(timezone.utc))
        service.record(entry)

        history = service.history("target-a")

        with pytest.raises(AttributeError):
            history.records = ()

        with pytest.raises(AttributeError):
            entry.operation = "unassign"
