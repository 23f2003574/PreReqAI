from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceAuditError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceAuditHistory,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceAuditRecord,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceAuditService,
)


def _record(audit_id, workspace_id, operation, timestamp, version=None, actor="system"):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceAuditRecord(
        audit_id=audit_id,
        workspace_id=workspace_id,
        operation=operation,
        version=version,
        timestamp=timestamp,
        actor=actor,
    )


class TestBindingWorkspaceAuditService:
    def test_record_audit_entry(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceAuditService()

        entry = _record("audit-1", "workspace-a", "create", datetime.now(timezone.utc))

        service.record(entry)

        assert service.list() == (entry,)

    def test_retrieve_workspace_history(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceAuditService()

        base = datetime.now(timezone.utc)
        first = _record("audit-1", "workspace-a", "create", base)
        second = _record("audit-2", "workspace-a", "publish", base + timedelta(seconds=5), version="1.0.0")
        other = _record("audit-3", "workspace-b", "create", base + timedelta(seconds=1))

        service.record(second)
        service.record(first)
        service.record(other)

        history = service.history("workspace-a")

        assert isinstance(history, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceAuditHistory)
        assert history.records == (first, second)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceAuditError):
            service.history("   ")

    def test_latest_entry(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceAuditService()

        base = datetime.now(timezone.utc)
        first = _record("audit-1", "workspace-a", "create", base)
        second = _record("audit-2", "workspace-a", "deploy", base + timedelta(seconds=5), version="1.0.0")

        service.record(first)
        service.record(second)

        assert service.latest("workspace-a") == second
        assert service.latest("workspace-unknown") is None

    def test_list_records(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceAuditService()

        base = datetime.now(timezone.utc)
        first = _record("audit-1", "workspace-a", "create", base + timedelta(seconds=10))
        second = _record("audit-2", "workspace-b", "create", base)

        service.record(first)
        service.record(second)

        assert service.list() == (second, first)

    def test_purge_old_records(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceAuditService()

        base = datetime.now(timezone.utc)
        old = _record("audit-1", "workspace-a", "create", base - timedelta(days=2))
        recent = _record("audit-2", "workspace-a", "publish", base, version="1.0.0")

        service.record(old)
        service.record(recent)

        purged_count = service.purge(base - timedelta(days=1))

        assert purged_count == 1
        assert service.list() == (recent,)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceAuditError):
            service.purge(None)

    def test_reject_duplicate_ids(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceAuditService()

        first = _record("audit-1", "workspace-a", "create", datetime.now(timezone.utc))
        duplicate = _record("audit-1", "workspace-b", "create", datetime.now(timezone.utc))

        service.record(first)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceAuditError):
            service.record(duplicate)

    def test_reject_invalid_records(self):
        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceAuditError):
            _record("   ", "workspace-a", "create", datetime.now(timezone.utc))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceAuditError):
            _record("audit-1", None, "create", datetime.now(timezone.utc))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceAuditError):
            _record("audit-1", "workspace-a", "invalid", datetime.now(timezone.utc))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceAuditError):
            _record("audit-1", "workspace-a", "create", None)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceAuditError):
            _record("audit-1", "workspace-a", "create", datetime.now(timezone.utc), actor="   ")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceAuditError):
            _record("audit-1", "workspace-a", "publish", datetime.now(timezone.utc), version="   ")

        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceAuditService()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceAuditError):
            service.record(None)

    def test_immutable_audit_history(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceAuditService()

        entry = _record("audit-1", "workspace-a", "create", datetime.now(timezone.utc))
        service.record(entry)

        history = service.history("workspace-a")

        with pytest.raises(AttributeError):
            history.records = ()

        with pytest.raises(AttributeError):
            entry.operation = "publish"
