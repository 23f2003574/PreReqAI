from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateAuditError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateAuditHistory,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateAuditRecord,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateAuditService,
)


def _record(audit_id, template_id, operation, timestamp, version=None, actor="system"):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateAuditRecord(
        audit_id=audit_id,
        template_id=template_id,
        operation=operation,
        version=version,
        timestamp=timestamp,
        actor=actor,
    )


class TestBindingTemplateAuditService:
    def test_record_audit_entry(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateAuditService()

        entry = _record("audit-1", "template-a", "register", datetime.now(timezone.utc))

        service.record(entry)

        assert service.list() == (entry,)

    def test_retrieve_template_history(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateAuditService()

        base = datetime.now(timezone.utc)
        first = _record("audit-1", "template-a", "register", base)
        second = _record("audit-2", "template-a", "publish", base + timedelta(seconds=5), version="1.0.0")
        other = _record("audit-3", "template-b", "register", base + timedelta(seconds=1))

        service.record(second)
        service.record(first)
        service.record(other)

        history = service.history("template-a")

        assert isinstance(history, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateAuditHistory)
        assert history.records == (first, second)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateAuditError):
            service.history("   ")

    def test_latest_entry(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateAuditService()

        base = datetime.now(timezone.utc)
        first = _record("audit-1", "template-a", "register", base)
        second = _record("audit-2", "template-a", "deploy", base + timedelta(seconds=5), version="1.0.0")

        service.record(first)
        service.record(second)

        assert service.latest("template-a") == second
        assert service.latest("template-unknown") is None

    def test_list_records(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateAuditService()

        base = datetime.now(timezone.utc)
        first = _record("audit-1", "template-a", "register", base + timedelta(seconds=10))
        second = _record("audit-2", "template-b", "register", base)

        service.record(first)
        service.record(second)

        assert service.list() == (second, first)

    def test_purge_old_records(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateAuditService()

        base = datetime.now(timezone.utc)
        old = _record("audit-1", "template-a", "register", base - timedelta(days=2))
        recent = _record("audit-2", "template-a", "publish", base, version="1.0.0")

        service.record(old)
        service.record(recent)

        purged_count = service.purge(base - timedelta(days=1))

        assert purged_count == 1
        assert service.list() == (recent,)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateAuditError):
            service.purge(None)

    def test_reject_duplicate_ids(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateAuditService()

        first = _record("audit-1", "template-a", "register", datetime.now(timezone.utc))
        duplicate = _record("audit-1", "template-b", "register", datetime.now(timezone.utc))

        service.record(first)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateAuditError):
            service.record(duplicate)

    def test_reject_invalid_records(self):
        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateAuditError):
            _record("   ", "template-a", "register", datetime.now(timezone.utc))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateAuditError):
            _record("audit-1", None, "register", datetime.now(timezone.utc))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateAuditError):
            _record("audit-1", "template-a", "invalid", datetime.now(timezone.utc))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateAuditError):
            _record("audit-1", "template-a", "register", None)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateAuditError):
            _record("audit-1", "template-a", "register", datetime.now(timezone.utc), actor="   ")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateAuditError):
            _record("audit-1", "template-a", "publish", datetime.now(timezone.utc), version="   ")

        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateAuditService()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateAuditError):
            service.record(None)

    def test_immutable_audit_history(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateAuditService()

        entry = _record("audit-1", "template-a", "register", datetime.now(timezone.utc))
        service.record(entry)

        history = service.history("template-a")

        with pytest.raises(AttributeError):
            history.records = ()

        with pytest.raises(AttributeError):
            entry.operation = "publish"
