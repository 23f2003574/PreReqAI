import dataclasses

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentHistory,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentHistoryError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentHistoryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentRecord,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentStatus,
)


def _record(
    deployment_id,
    binding_id,
    environment,
    version,
    deployed_at,
    status=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentStatus.SUCCEEDED,
):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentRecord(
        deployment_id=deployment_id,
        binding_id=binding_id,
        environment=environment,
        version=version,
        deployed_at=deployed_at,
        status=status,
    )


class TestRecordDeployment:
    def test_record_deployment(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentHistoryService()

        record = _record("deployment-1", "binding-1", "production", "1.0.0", datetime.now(timezone.utc))
        service.record(record)

        assert service.find("deployment-1") == record


class TestDeploymentLookup:
    def test_deployment_lookup_missing(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentHistoryService()

        assert service.find("deployment-missing") is None


class TestBindingHistory:
    def test_binding_history_chronological(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentHistoryService()

        base = datetime.now(timezone.utc)
        first = _record("deployment-1", "binding-1", "production", "1.0.0", base)
        second = _record("deployment-2", "binding-1", "staging", "1.1.0", base + timedelta(minutes=5))
        other = _record("deployment-3", "binding-2", "production", "2.0.0", base + timedelta(minutes=1))

        service.record(first)
        service.record(second)
        service.record(other)

        assert service.history("binding-1") == (first, second)


class TestEnvironmentHistory:
    def test_environment_history(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentHistoryService()

        base = datetime.now(timezone.utc)
        first = _record("deployment-1", "binding-1", "production", "1.0.0", base)
        second = _record("deployment-2", "binding-2", "production", "2.0.0", base + timedelta(minutes=1))
        other = _record("deployment-3", "binding-3", "staging", "1.0.0", base + timedelta(minutes=2))

        service.record(first)
        service.record(second)
        service.record(other)

        assert service.history_for_environment("production") == (first, second)


class TestLatestDeployment:
    def test_latest_deployment(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentHistoryService()

        base = datetime.now(timezone.utc)
        first = _record("deployment-1", "binding-1", "production", "1.0.0", base)
        second = _record("deployment-2", "binding-1", "production", "2.0.0", base + timedelta(minutes=5))

        service.record(first)
        service.record(second)

        assert service.latest("binding-1") == second
        assert service.latest("binding-missing") is None


class TestDuplicateRejection:
    def test_reject_duplicate_deployment_id(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentHistoryService()

        base = datetime.now(timezone.utc)
        service.record(_record("deployment-1", "binding-1", "production", "1.0.0", base))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentHistoryError):
            service.record(_record("deployment-1", "binding-2", "staging", "1.0.0", base))

    def test_reject_none_record(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentHistoryService()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentHistoryError):
            service.record(None)

    def test_reject_blank_ids(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentHistoryService()
        base = datetime.now(timezone.utc)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentHistoryError):
            service.record(_record("   ", "binding-1", "production", "1.0.0", base))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentHistoryError):
            service.record(_record("deployment-1", None, "production", "1.0.0", base))

    def test_reject_invalid_status(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentHistoryService()

        malformed = _record("deployment-1", "binding-1", "production", "1.0.0", datetime.now(timezone.utc))
        malformed = dataclasses.replace(malformed, status="not-a-real-status")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentHistoryError):
            service.record(malformed)


class TestImmutableHistory:
    def test_immutable_record(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentHistoryService()

        record = _record("deployment-1", "binding-1", "production", "1.0.0", datetime.now(timezone.utc))
        service.record(record)

        with pytest.raises(dataclasses.FrozenInstanceError):
            record.status = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentStatus.FAILED

    def test_immutable_history_object(self):
        history = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentHistory(records=())

        with pytest.raises(dataclasses.FrozenInstanceError):
            history.records = ()
