import dataclasses

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentHistory,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentHistoryError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentHistoryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentRecord,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentStatus,
)


def _record(
    deployment_id,
    preset_id,
    environment,
    version,
    deployed_at,
    instantiated_binding_ids=(),
    status=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentStatus.SUCCEEDED,
):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentRecord(
        deployment_id=deployment_id,
        preset_id=preset_id,
        environment=environment,
        version=version,
        instantiated_binding_ids=instantiated_binding_ids,
        deployed_at=deployed_at,
        status=status,
    )


class TestRecordDeployment:
    def test_record_deployment(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentHistoryService()

        record = _record(
            "deployment-1",
            "preset-1",
            "production",
            "v1",
            datetime.now(timezone.utc),
            instantiated_binding_ids=("binding-1", "binding-2"),
        )
        service.record(record)

        assert service.find("deployment-1") == record


class TestDeploymentLookup:
    def test_deployment_lookup_missing(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentHistoryService()

        assert service.find("deployment-missing") is None


class TestPresetHistory:
    def test_preset_history_chronological(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentHistoryService()

        base = datetime.now(timezone.utc)
        first = _record("deployment-1", "preset-1", "production", "v1", base)
        second = _record("deployment-2", "preset-1", "staging", "v2", base + timedelta(minutes=5))
        other = _record("deployment-3", "preset-2", "production", "v1", base + timedelta(minutes=1))

        service.record(first)
        service.record(second)
        service.record(other)

        assert service.history("preset-1") == (first, second)


class TestEnvironmentHistory:
    def test_environment_history(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentHistoryService()

        base = datetime.now(timezone.utc)
        first = _record("deployment-1", "preset-1", "production", "v1", base)
        second = _record("deployment-2", "preset-2", "production", "v2", base + timedelta(minutes=1))
        other = _record("deployment-3", "preset-3", "staging", "v1", base + timedelta(minutes=2))

        service.record(first)
        service.record(second)
        service.record(other)

        assert service.history_for_environment("production") == (first, second)


class TestLatestDeployment:
    def test_latest_deployment(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentHistoryService()

        base = datetime.now(timezone.utc)
        first = _record("deployment-1", "preset-1", "production", "v1", base)
        second = _record("deployment-2", "preset-1", "production", "v2", base + timedelta(minutes=5))

        service.record(first)
        service.record(second)

        assert service.latest("preset-1") == second
        assert service.latest("preset-missing") is None


class TestDuplicateRejection:
    def test_reject_duplicate_deployment_id(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentHistoryService()

        base = datetime.now(timezone.utc)
        service.record(_record("deployment-1", "preset-1", "production", "v1", base))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentHistoryError):
            service.record(_record("deployment-1", "preset-2", "staging", "v1", base))

    def test_reject_none_record(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentHistoryService()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentHistoryError):
            service.record(None)

    def test_reject_blank_ids(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentHistoryService()
        base = datetime.now(timezone.utc)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentHistoryError):
            service.record(_record("   ", "preset-1", "production", "v1", base))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentHistoryError):
            service.record(_record("deployment-1", None, "production", "v1", base))

    def test_reject_invalid_status(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentHistoryService()

        malformed = _record("deployment-1", "preset-1", "production", "v1", datetime.now(timezone.utc))
        malformed = dataclasses.replace(malformed, status="not-a-real-status")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentHistoryError):
            service.record(malformed)


class TestImmutableHistory:
    def test_immutable_record(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentHistoryService()

        record = _record("deployment-1", "preset-1", "production", "v1", datetime.now(timezone.utc))
        service.record(record)

        with pytest.raises(dataclasses.FrozenInstanceError):
            record.status = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentStatus.FAILED

    def test_immutable_history_object(self):
        history = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentHistory(records=())

        with pytest.raises(dataclasses.FrozenInstanceError):
            history.records = ()
