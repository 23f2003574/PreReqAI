from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetAuditError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetAuditHistory,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetAuditRecord,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetAuditService,
)


def _record(audit_id, preset_id, operation, timestamp, version=None, actor="system"):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetAuditRecord(
        audit_id=audit_id,
        preset_id=preset_id,
        operation=operation,
        version=version,
        timestamp=timestamp,
        actor=actor,
    )


class TestBindingPresetAuditService:
    def test_record_audit_entry(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetAuditService()

        entry = _record("audit-1", "preset-a", "register", datetime.now(timezone.utc))

        service.record(entry)

        assert service.list() == (entry,)

    def test_retrieve_preset_history(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetAuditService()

        base = datetime.now(timezone.utc)
        first = _record("audit-1", "preset-a", "register", base)
        second = _record("audit-2", "preset-a", "publish", base + timedelta(seconds=5), version="1.0.0")
        other = _record("audit-3", "preset-b", "register", base + timedelta(seconds=1))

        service.record(second)
        service.record(first)
        service.record(other)

        history = service.history("preset-a")

        assert isinstance(history, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetAuditHistory)
        assert history.records == (first, second)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetAuditError):
            service.history("   ")

    def test_latest_entry(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetAuditService()

        base = datetime.now(timezone.utc)
        first = _record("audit-1", "preset-a", "register", base)
        second = _record("audit-2", "preset-a", "deploy", base + timedelta(seconds=5), version="1.0.0")

        service.record(first)
        service.record(second)

        assert service.latest("preset-a") == second
        assert service.latest("preset-unknown") is None

    def test_list_records(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetAuditService()

        base = datetime.now(timezone.utc)
        first = _record("audit-1", "preset-a", "register", base + timedelta(seconds=10))
        second = _record("audit-2", "preset-b", "register", base)

        service.record(first)
        service.record(second)

        assert service.list() == (second, first)

    def test_purge_old_records(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetAuditService()

        base = datetime.now(timezone.utc)
        old = _record("audit-1", "preset-a", "register", base - timedelta(days=2))
        recent = _record("audit-2", "preset-a", "publish", base, version="1.0.0")

        service.record(old)
        service.record(recent)

        purged_count = service.purge(base - timedelta(days=1))

        assert purged_count == 1
        assert service.list() == (recent,)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetAuditError):
            service.purge(None)

    def test_reject_duplicate_ids(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetAuditService()

        first = _record("audit-1", "preset-a", "register", datetime.now(timezone.utc))
        duplicate = _record("audit-1", "preset-b", "register", datetime.now(timezone.utc))

        service.record(first)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetAuditError):
            service.record(duplicate)

    def test_reject_invalid_records(self):
        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetAuditError):
            _record("   ", "preset-a", "register", datetime.now(timezone.utc))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetAuditError):
            _record("audit-1", None, "register", datetime.now(timezone.utc))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetAuditError):
            _record("audit-1", "preset-a", "invalid", datetime.now(timezone.utc))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetAuditError):
            _record("audit-1", "preset-a", "register", None)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetAuditError):
            _record("audit-1", "preset-a", "register", datetime.now(timezone.utc), actor="   ")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetAuditError):
            _record("audit-1", "preset-a", "publish", datetime.now(timezone.utc), version="   ")

        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetAuditService()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetAuditError):
            service.record(None)

    def test_immutable_audit_history(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetAuditService()

        entry = _record("audit-1", "preset-a", "register", datetime.now(timezone.utc))
        service.record(entry)

        history = service.history("preset-a")

        with pytest.raises(AttributeError):
            history.records = ()

        with pytest.raises(AttributeError):
            entry.operation = "publish"
