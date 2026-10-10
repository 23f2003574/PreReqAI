import dataclasses

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentHistory,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentHistoryError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentHistoryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentRecord,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentStatus,
)


def _record(
    deployment_id,
    template_id,
    environment,
    version,
    deployed_at,
    instantiated_binding_ids=(),
    status=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentStatus.SUCCEEDED,
):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentRecord(
        deployment_id=deployment_id,
        template_id=template_id,
        environment=environment,
        version=version,
        instantiated_binding_ids=instantiated_binding_ids,
        deployed_at=deployed_at,
        status=status,
    )


class TestRecordDeployment:
    def test_record_deployment(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentHistoryService()

        record = _record(
            "deployment-1",
            "template-1",
            "production",
            "v1",
            datetime.now(timezone.utc),
            instantiated_binding_ids=("binding-1", "binding-2"),
        )
        service.record(record)

        assert service.find("deployment-1") == record


class TestDeploymentLookup:
    def test_deployment_lookup_missing(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentHistoryService()

        assert service.find("deployment-missing") is None


class TestTemplateHistory:
    def test_template_history_chronological(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentHistoryService()

        base = datetime.now(timezone.utc)
        first = _record("deployment-1", "template-1", "production", "v1", base)
        second = _record("deployment-2", "template-1", "staging", "v2", base + timedelta(minutes=5))
        other = _record("deployment-3", "template-2", "production", "v1", base + timedelta(minutes=1))

        service.record(first)
        service.record(second)
        service.record(other)

        assert service.history("template-1") == (first, second)


class TestEnvironmentHistory:
    def test_environment_history(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentHistoryService()

        base = datetime.now(timezone.utc)
        first = _record("deployment-1", "template-1", "production", "v1", base)
        second = _record("deployment-2", "template-2", "production", "v2", base + timedelta(minutes=1))
        other = _record("deployment-3", "template-3", "staging", "v1", base + timedelta(minutes=2))

        service.record(first)
        service.record(second)
        service.record(other)

        assert service.history_for_environment("production") == (first, second)


class TestLatestDeployment:
    def test_latest_deployment(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentHistoryService()

        base = datetime.now(timezone.utc)
        first = _record("deployment-1", "template-1", "production", "v1", base)
        second = _record("deployment-2", "template-1", "production", "v2", base + timedelta(minutes=5))

        service.record(first)
        service.record(second)

        assert service.latest("template-1") == second
        assert service.latest("template-missing") is None


class TestDuplicateRejection:
    def test_reject_duplicate_deployment_id(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentHistoryService()

        base = datetime.now(timezone.utc)
        service.record(_record("deployment-1", "template-1", "production", "v1", base))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentHistoryError):
            service.record(_record("deployment-1", "template-2", "staging", "v1", base))

    def test_reject_none_record(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentHistoryService()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentHistoryError):
            service.record(None)

    def test_reject_blank_ids(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentHistoryService()
        base = datetime.now(timezone.utc)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentHistoryError):
            service.record(_record("   ", "template-1", "production", "v1", base))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentHistoryError):
            service.record(_record("deployment-1", None, "production", "v1", base))

    def test_reject_invalid_status(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentHistoryService()

        malformed = _record("deployment-1", "template-1", "production", "v1", datetime.now(timezone.utc))
        malformed = dataclasses.replace(malformed, status="not-a-real-status")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentHistoryError):
            service.record(malformed)


class TestImmutableHistory:
    def test_immutable_record(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentHistoryService()

        record = _record("deployment-1", "template-1", "production", "v1", datetime.now(timezone.utc))
        service.record(record)

        with pytest.raises(dataclasses.FrozenInstanceError):
            record.status = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentStatus.FAILED

    def test_immutable_history_object(self):
        history = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentHistory(records=())

        with pytest.raises(dataclasses.FrozenInstanceError):
            history.records = ()
