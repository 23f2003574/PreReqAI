import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroup,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSyncError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSyncRequest,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSyncResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSynchronizationService,
)


class FakeTargetGateway:
    def __init__(self, failing=()):
        self.failing = set(failing)
        self.calls = []

    def push(self, group_id, target):
        self.calls.append((group_id, target))

        return (group_id, target) not in self.failing


def _group(group_id, binding_ids=()):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroup(
        group_id=group_id,
        group_name=group_id,
        binding_ids=binding_ids,
    )


def _build_service(groups=(("group-1", ("binding-1",)),), failing=()):
    group_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryService()

    for group_id, binding_ids in groups:
        group_registry.register(_group(group_id, binding_ids=binding_ids))

    gateway = FakeTargetGateway(failing=failing)

    service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSynchronizationService(
        group_registry,
        gateway,
    )

    return service, group_registry, gateway


class TestSyncSingleGroup:
    def test_sync_single_group(self):
        service, _, _ = _build_service()

        result = service.sync_target("group-1", "registry")

        assert isinstance(result, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSyncResult)
        assert result.synchronized is True
        assert result.synchronized_targets == ("registry",)
        assert len(service.pending()) == 1

        applied = service.sync_all()

        assert applied.synchronized is True
        assert applied.synchronized_targets == ("registry",)
        assert applied.failed_targets == ()
        assert service.is_synchronized("group-1") is True
        assert service.pending() == ()


class TestSyncAllGroups:
    def test_sync_all_groups(self):
        service, _, _ = _build_service(groups=(("group-1", ("binding-1",)), ("group-2", ("binding-2",))))

        service.sync_target("group-1", "registry")
        service.sync_target("group-2", "cache")

        result = service.sync_all()

        assert result.synchronized is True
        assert result.synchronized_targets == ("registry", "cache")
        assert service.is_synchronized("group-1") is True
        assert service.is_synchronized("group-2") is True
        assert service.pending() == ()


class TestSyncSpecificTarget:
    def test_sync_specific_target(self):
        service, _, _ = _build_service()

        service.sync_target("group-1", "registry")
        service.sync_target("group-1", "cache")
        service.sync_all()

        assert service.is_synchronized("group-1") is True

        result = service.sync("group-1")

        assert result.synchronized is False
        assert result.synchronized_targets == ()


class TestRetryFailedSync:
    def test_retry_failed_synchronization(self):
        service, _, gateway = _build_service(failing=(("group-1", "cache"),))

        service.sync_target("group-1", "cache")
        first_apply = service.sync_all()

        assert first_apply.synchronized is False
        assert first_apply.failed_targets == ("cache",)
        assert service.is_synchronized("group-1") is False

        gateway.failing.discard(("group-1", "cache"))

        retried = service.sync("group-1")

        assert retried.synchronized_targets == ("cache",)

        second_apply = service.sync_all()

        assert second_apply.synchronized is True
        assert second_apply.synchronized_targets == ("cache",)
        assert second_apply.failed_targets == ()
        assert service.is_synchronized("group-1") is True


class TestPendingSyncLookup:
    def test_pending_synchronization(self):
        service, _, _ = _build_service()

        service.sync_target("group-1", "registry")

        pending = service.pending()

        assert len(pending) == 1
        assert pending[0].group_id == "group-1"
        assert pending[0].target == "registry"


class TestIdempotentSynchronization:
    def test_idempotent_when_unchanged(self):
        service, _, _ = _build_service()

        service.sync_target("group-1", "registry")
        service.sync_all()

        second = service.sync_target("group-1", "registry")

        assert second.synchronized is False
        assert second.synchronized_targets == ()
        assert service.pending() == ()

    def test_reject_duplicate_pending_synchronization(self):
        service, _, _ = _build_service()

        service.sync_target("group-1", "registry")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSyncError):
            service.sync_target("group-1", "registry")


class TestInvalidRequestRejection:
    def test_reject_blank_ids(self):
        service, _, _ = _build_service()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSyncError):
            service.sync_target("   ", "registry")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSyncError):
            service.sync_target("group-1", None)

    def test_reject_unknown_group(self):
        service, _, _ = _build_service()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSyncError):
            service.sync_target("group-missing", "registry")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSyncError):
            service.sync("group-missing")

    def test_reject_invalid_operation(self):
        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSyncError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSyncRequest(
                group_id="group-1",
                operation="invalid",
                target="registry",
            )

    def test_reject_none_dependencies(self):
        group_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryService()
        gateway = FakeTargetGateway()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSyncError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSynchronizationService(None, gateway)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSyncError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSynchronizationService(group_registry, None)


class TestImmutableSyncResults:
    def test_immutable_result(self):
        service, _, _ = _build_service()

        result = service.sync_target("group-1", "registry")

        with pytest.raises(AttributeError):
            result.synchronized = False
