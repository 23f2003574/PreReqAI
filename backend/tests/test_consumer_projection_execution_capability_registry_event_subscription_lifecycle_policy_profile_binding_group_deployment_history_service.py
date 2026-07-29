import dataclasses

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentHistory,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentHistoryError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentHistoryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentRecord,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentStatus,
)


def _record(
    deployment_id,
    group_id,
    environment,
    version,
    deployed_at,
    status=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentStatus.SUCCEEDED,
):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentRecord(
        deployment_id=deployment_id,
        group_id=group_id,
        environment=environment,
        version=version,
        deployed_at=deployed_at,
        status=status,
    )


class TestRecordDeployment:
    def test_record_deployment(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentHistoryService()

        record = _record("deployment-1", "group-1", "production", "v1", datetime.now(timezone.utc))
        service.record(record)

        assert service.find("deployment-1") == record


class TestDeploymentLookup:
    def test_deployment_lookup_missing(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentHistoryService()

        assert service.find("deployment-missing") is None


class TestGroupHistory:
    def test_group_history_chronological(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentHistoryService()

        base = datetime.now(timezone.utc)
        first = _record("deployment-1", "group-1", "production", "v1", base)
        second = _record("deployment-2", "group-1", "staging", "v2", base + timedelta(minutes=5))
        other = _record("deployment-3", "group-2", "production", "v1", base + timedelta(minutes=1))

        service.record(first)
        service.record(second)
        service.record(other)

        assert service.history("group-1") == (first, second)


class TestEnvironmentHistory:
    def test_environment_history(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentHistoryService()

        base = datetime.now(timezone.utc)
        first = _record("deployment-1", "group-1", "production", "v1", base)
        second = _record("deployment-2", "group-2", "production", "v2", base + timedelta(minutes=1))
        other = _record("deployment-3", "group-3", "staging", "v1", base + timedelta(minutes=2))

        service.record(first)
        service.record(second)
        service.record(other)

        assert service.history_for_environment("production") == (first, second)


class TestLatestDeployment:
    def test_latest_deployment(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentHistoryService()

        base = datetime.now(timezone.utc)
        first = _record("deployment-1", "group-1", "production", "v1", base)
        second = _record("deployment-2", "group-1", "production", "v2", base + timedelta(minutes=5))

        service.record(first)
        service.record(second)

        assert service.latest("group-1") == second
        assert service.latest("group-missing") is None


class TestDuplicateRejection:
    def test_reject_duplicate_deployment_id(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentHistoryService()

        base = datetime.now(timezone.utc)
        service.record(_record("deployment-1", "group-1", "production", "v1", base))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentHistoryError):
            service.record(_record("deployment-1", "group-2", "staging", "v1", base))

    def test_reject_none_record(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentHistoryService()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentHistoryError):
            service.record(None)

    def test_reject_blank_ids(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentHistoryService()
        base = datetime.now(timezone.utc)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentHistoryError):
            service.record(_record("   ", "group-1", "production", "v1", base))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentHistoryError):
            service.record(_record("deployment-1", None, "production", "v1", base))

    def test_reject_invalid_status(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentHistoryService()

        malformed = _record("deployment-1", "group-1", "production", "v1", datetime.now(timezone.utc))
        malformed = dataclasses.replace(malformed, status="not-a-real-status")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentHistoryError):
            service.record(malformed)


class TestImmutableHistory:
    def test_immutable_record(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentHistoryService()

        record = _record("deployment-1", "group-1", "production", "v1", datetime.now(timezone.utc))
        service.record(record)

        with pytest.raises(dataclasses.FrozenInstanceError):
            record.status = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentStatus.FAILED

    def test_immutable_history_object(self):
        history = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentHistory(records=())

        with pytest.raises(dataclasses.FrozenInstanceError):
            history.records = ()
