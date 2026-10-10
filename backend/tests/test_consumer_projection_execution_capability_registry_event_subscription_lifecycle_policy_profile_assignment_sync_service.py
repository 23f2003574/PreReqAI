import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfile,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSyncError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSyncRequest,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSyncResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSynchronizationService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileService,
)


def _build_profile(profile_id):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfile(
        profile_id=profile_id,
        profile_name=profile_id,
        description=f"Profile {profile_id}.",
        policy_identifiers=(f"policy-{profile_id}",),
    )


def _build_service(profile_ids=("development",)):
    profile_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileService()

    for profile_id in profile_ids:
        profile_service.register(_build_profile(profile_id))

    assignment_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentService(profile_service)
    assignment_service.assign("target-a", "development")

    sync_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSynchronizationService(
        assignment_service,
        profile_service,
    )

    return sync_service, assignment_service


class TestProfileAssignmentSynchronizationService:
    def test_synchronize_assignment(self):
        sync_service, _ = _build_service()

        request = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSyncRequest(
            target_id="target-a",
            profile_id="development",
            operation="register",
        )

        result = sync_service.sync(request)

        assert isinstance(result, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSyncResult)
        assert result.synchronized is True
        assert result.synchronized_targets == ("target-a",)
        assert len(sync_service.pending()) == 1

        applied = sync_service.sync_all()
        assert applied.synchronized is True
        assert applied.synchronized_targets == ("target-a",)
        assert sync_service.is_synchronized("target-a") is True
        assert sync_service.pending() == ()

    def test_synchronize_all(self):
        sync_service, _ = _build_service(profile_ids=("development", "staging"))

        first = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSyncRequest(
            target_id="target-a",
            profile_id="development",
            operation="register",
        )
        second = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSyncRequest(
            target_id="target-b",
            profile_id="staging",
            operation="register",
        )

        sync_service.sync(first)
        sync_service.sync(second)

        result = sync_service.sync_all()

        assert result.synchronized is True
        assert result.synchronized_targets == ("target-a", "target-b")
        assert sync_service.is_synchronized("target-a") is True
        assert sync_service.is_synchronized("target-b") is True
        assert sync_service.pending() == ()

    def test_idempotent_sync(self):
        sync_service, _ = _build_service()

        request = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSyncRequest(
            target_id="target-a",
            profile_id="development",
            operation="register",
        )

        first = sync_service.sync(request)
        second = sync_service.sync(request)

        assert first.synchronized is True
        assert second.synchronized is False
        assert second.synchronized_targets == ()
        assert sync_service.pending() == (request,)

        applied = sync_service.sync_all()
        assert applied.synchronized is True
        assert applied.synchronized_targets == ("target-a",)

    def test_pending_synchronization(self):
        sync_service, _ = _build_service()

        request = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSyncRequest(
            target_id="target-a",
            profile_id="development",
            operation="register",
        )

        sync_service.sync(request)

        assert sync_service.pending() == (request,)

    def test_synchronization_status(self):
        sync_service, _ = _build_service()

        assert sync_service.is_synchronized("target-a") is False

        request = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSyncRequest(
            target_id="target-a",
            profile_id="development",
            operation="register",
        )

        sync_service.sync(request)
        sync_service.sync_all()

        assert sync_service.is_synchronized("target-a") is True
        assert sync_service.is_synchronized("target-z") is False

    def test_reject_invalid_requests(self):
        sync_service, _ = _build_service()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSyncError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSyncRequest(
                target_id="   ",
                profile_id="development",
                operation="register",
            )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSyncError):
            sync_service.sync(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSyncRequest(
                    target_id="target-a",
                    profile_id="missing",
                    operation="register",
                )
            )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSyncError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSyncRequest(
                target_id="target-a",
                profile_id=None,
                operation="register",
            )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSyncError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSyncRequest(
                target_id="target-a",
                profile_id="development",
                operation="invalid",
            )

    def test_reject_duplicate_pending_synchronization(self):
        sync_service, _ = _build_service()

        first = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSyncRequest(
            target_id="target-a",
            profile_id="development",
            operation="register",
        )
        second = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSyncRequest(
            target_id="target-a",
            profile_id="development",
            operation="register",
        )

        sync_service.sync(first)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSyncError):
            sync_service.sync(second)

    def test_immutable_sync_results(self):
        sync_service, _ = _build_service()

        request = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSyncRequest(
            target_id="target-a",
            profile_id="development",
            operation="register",
        )

        result = sync_service.sync(request)

        with pytest.raises(AttributeError):
            result.synchronized = False
