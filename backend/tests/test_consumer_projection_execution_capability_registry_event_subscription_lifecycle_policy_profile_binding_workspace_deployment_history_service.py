import dataclasses

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentHistory,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentHistoryError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentHistoryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentRecord,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentStatus,
)


def _record(
    deployment_id,
    workspace_id,
    environment,
    version,
    deployed_at,
    deployed_resources=None,
    status=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentStatus.SUCCEEDED,
):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentRecord(
        deployment_id=deployment_id,
        workspace_id=workspace_id,
        environment=environment,
        version=version,
        deployed_resources=deployed_resources if deployed_resources is not None else {},
        deployed_at=deployed_at,
        status=status,
    )


class TestRecordDeployment:
    def test_record_deployment(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentHistoryService()

        record = _record(
            "deployment-1",
            "workspace-1",
            "production",
            "v1",
            datetime.now(timezone.utc),
            deployed_resources={"bindings": ("binding-1", "binding-2")},
        )
        service.record(record)

        assert service.find("deployment-1") == record


class TestDeploymentLookup:
    def test_deployment_lookup_missing(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentHistoryService()

        assert service.find("deployment-missing") is None


class TestWorkspaceHistory:
    def test_workspace_history_chronological(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentHistoryService()

        base = datetime.now(timezone.utc)
        first = _record("deployment-1", "workspace-1", "production", "v1", base)
        second = _record("deployment-2", "workspace-1", "staging", "v2", base + timedelta(minutes=5))
        other = _record("deployment-3", "workspace-2", "production", "v1", base + timedelta(minutes=1))

        service.record(first)
        service.record(second)
        service.record(other)

        assert service.history("workspace-1") == (first, second)


class TestEnvironmentHistory:
    def test_environment_history(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentHistoryService()

        base = datetime.now(timezone.utc)
        first = _record("deployment-1", "workspace-1", "production", "v1", base)
        second = _record("deployment-2", "workspace-2", "production", "v2", base + timedelta(minutes=1))
        other = _record("deployment-3", "workspace-3", "staging", "v1", base + timedelta(minutes=2))

        service.record(first)
        service.record(second)
        service.record(other)

        assert service.history_for_environment("production") == (first, second)


class TestLatestDeployment:
    def test_latest_deployment(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentHistoryService()

        base = datetime.now(timezone.utc)
        first = _record("deployment-1", "workspace-1", "production", "v1", base)
        second = _record("deployment-2", "workspace-1", "production", "v2", base + timedelta(minutes=5))

        service.record(first)
        service.record(second)

        assert service.latest("workspace-1") == second
        assert service.latest("workspace-missing") is None


class TestDuplicateRejection:
    def test_reject_duplicate_deployment_id(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentHistoryService()

        base = datetime.now(timezone.utc)
        service.record(_record("deployment-1", "workspace-1", "production", "v1", base))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentHistoryError):
            service.record(_record("deployment-1", "workspace-2", "staging", "v1", base))

    def test_reject_none_record(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentHistoryService()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentHistoryError):
            service.record(None)

    def test_reject_blank_ids(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentHistoryService()
        base = datetime.now(timezone.utc)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentHistoryError):
            service.record(_record("   ", "workspace-1", "production", "v1", base))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentHistoryError):
            service.record(_record("deployment-1", None, "production", "v1", base))

    def test_reject_invalid_status(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentHistoryService()

        malformed = _record("deployment-1", "workspace-1", "production", "v1", datetime.now(timezone.utc))
        malformed = dataclasses.replace(malformed, status="not-a-real-status")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentHistoryError):
            service.record(malformed)


class TestImmutableHistory:
    def test_immutable_record(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentHistoryService()

        record = _record("deployment-1", "workspace-1", "production", "v1", datetime.now(timezone.utc))
        service.record(record)

        with pytest.raises(dataclasses.FrozenInstanceError):
            record.status = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentStatus.FAILED

    def test_immutable_history_object(self):
        history = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentHistory(records=())

        with pytest.raises(dataclasses.FrozenInstanceError):
            history.records = ()
