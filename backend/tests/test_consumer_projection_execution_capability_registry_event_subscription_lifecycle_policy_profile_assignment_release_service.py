import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRelease,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentReleaseError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentReleaseResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentReleaseService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentReleaseStatus,
)


class TestProfileAssignmentReleaseService:
    def test_release_version(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentReleaseService()

        result = service.release("v1")

        assert isinstance(result, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentReleaseResult)
        assert result.previous_status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentReleaseStatus.DRAFT
        assert result.current_status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentReleaseStatus.RELEASED
        assert isinstance(result.release, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRelease)
        assert result.release.version == "v1"
        assert result.release.released_at is not None

    def test_retire_version(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentReleaseService()

        service.release("v1")
        result = service.retire("v1")

        assert result.previous_status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentReleaseStatus.RELEASED
        assert result.current_status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentReleaseStatus.RETIRED
        assert result.release.version == "v1"
        assert service.is_released("v1") is False

    def test_latest_release(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentReleaseService()

        assert service.latest_release() is None

        service.release("v1")
        latest = service.release("v2")

        assert service.latest_release() == latest.release

        service.retire("v2")

        assert service.latest_release().version == "v1"

    def test_is_released_true_and_false(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentReleaseService()

        assert service.is_released("v1") is False

        service.release("v1")

        assert service.is_released("v1") is True

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentReleaseError):
            service.is_released("   ")

    def test_duplicate_release_rejection(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentReleaseService()

        service.release("v1")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentReleaseError):
            service.release("v1")

    def test_invalid_transition_rejection(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentReleaseService()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentReleaseError):
            service.retire("v1")

        service.release("v1")
        service.retire("v1")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentReleaseError):
            service.retire("v1")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentReleaseError):
            service.release("v1")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentReleaseError):
            service.release("   ")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentReleaseError):
            service.release(None)

    def test_immutable_release_history(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentReleaseService()

        released = service.release("v1").release

        with pytest.raises(AttributeError):
            released.status = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentReleaseStatus.RETIRED

        retired_result = service.retire("v1")

        assert released.status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentReleaseStatus.RELEASED
        assert retired_result.release.status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentReleaseStatus.RETIRED
        assert retired_result.release.release_id == released.release_id

        with pytest.raises(AttributeError):
            retired_result.release = None
