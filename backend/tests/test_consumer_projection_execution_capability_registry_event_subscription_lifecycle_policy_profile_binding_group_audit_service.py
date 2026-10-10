from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupAuditError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupAuditHistory,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupAuditRecord,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupAuditService,
)


def _record(audit_id, group_id, operation, timestamp, actor="system"):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupAuditRecord(
        audit_id=audit_id,
        group_id=group_id,
        operation=operation,
        timestamp=timestamp,
        actor=actor,
    )


class TestBindingGroupAuditService:
    def test_record_audit_entry(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupAuditService()

        entry = _record("audit-1", "group-a", "create", datetime.now(timezone.utc))

        service.record(entry)

        assert service.list() == (entry,)

    def test_retrieve_group_history(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupAuditService()

        base = datetime.now(timezone.utc)
        first = _record("audit-1", "group-a", "create", base)
        second = _record("audit-2", "group-a", "update", base + timedelta(seconds=5))
        other = _record("audit-3", "group-b", "create", base + timedelta(seconds=1))

        service.record(second)
        service.record(first)
        service.record(other)

        history = service.history("group-a")

        assert isinstance(history, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupAuditHistory)
        assert history.records == (first, second)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupAuditError):
            service.history("   ")

    def test_latest_entry(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupAuditService()

        base = datetime.now(timezone.utc)
        first = _record("audit-1", "group-a", "create", base)
        second = _record("audit-2", "group-a", "deploy", base + timedelta(seconds=5))

        service.record(first)
        service.record(second)

        assert service.latest("group-a") == second
        assert service.latest("group-unknown") is None

    def test_list_records(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupAuditService()

        base = datetime.now(timezone.utc)
        first = _record("audit-1", "group-a", "create", base + timedelta(seconds=10))
        second = _record("audit-2", "group-b", "create", base)

        service.record(first)
        service.record(second)

        assert service.list() == (second, first)

    def test_purge_old_records(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupAuditService()

        base = datetime.now(timezone.utc)
        old = _record("audit-1", "group-a", "create", base - timedelta(days=2))
        recent = _record("audit-2", "group-a", "update", base)

        service.record(old)
        service.record(recent)

        purged_count = service.purge(base - timedelta(days=1))

        assert purged_count == 1
        assert service.list() == (recent,)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupAuditError):
            service.purge(None)

    def test_reject_duplicate_ids(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupAuditService()

        first = _record("audit-1", "group-a", "create", datetime.now(timezone.utc))
        duplicate = _record("audit-1", "group-b", "create", datetime.now(timezone.utc))

        service.record(first)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupAuditError):
            service.record(duplicate)

    def test_reject_invalid_records(self):
        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupAuditError):
            _record("   ", "group-a", "create", datetime.now(timezone.utc))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupAuditError):
            _record("audit-1", None, "create", datetime.now(timezone.utc))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupAuditError):
            _record("audit-1", "group-a", "invalid", datetime.now(timezone.utc))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupAuditError):
            _record("audit-1", "group-a", "create", None)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupAuditError):
            _record("audit-1", "group-a", "create", datetime.now(timezone.utc), actor="   ")

        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupAuditService()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupAuditError):
            service.record(None)

    def test_immutable_audit_history(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupAuditService()

        entry = _record("audit-1", "group-a", "create", datetime.now(timezone.utc))
        service.record(entry)

        history = service.history("group-a")

        with pytest.raises(AttributeError):
            history.records = ()

        with pytest.raises(AttributeError):
            entry.operation = "update"
