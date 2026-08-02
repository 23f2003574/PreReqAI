import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspace,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceReleaseService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSyncError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSyncRequest,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSyncResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSynchronizationService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryService,
)


class FakeTargetGateway:
    def __init__(self, failing=()):
        self.failing = set(failing)
        self.calls = []

    def push(self, workspace_id, target):
        self.calls.append((workspace_id, target))

        return (workspace_id, target) not in self.failing


def _workspace(workspace_id, binding_ids=()):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspace(
        workspace_id=workspace_id,
        name=workspace_id,
        description="A workspace.",
        binding_ids=binding_ids,
        template_ids=(),
        preset_ids=(),
        group_ids=(),
    )


def _build_service(workspaces=(("workspace-1", ()),), failing=()):
    binding_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryService()
    template_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryService()
    preset_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryService()
    group_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryService()

    workspace_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRegistryService()

    workspace_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceService(
        binding_registry, template_registry, preset_registry, group_registry
    )

    for workspace_id, binding_ids in workspaces:
        workspace = _workspace(workspace_id, binding_ids=binding_ids)
        workspace_registry.register(workspace)
        workspace_service.create(workspace)

    workspace_version_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionService(
        workspace_service
    )

    release_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceReleaseService(
        workspace_registry,
        workspace_version_service,
    )

    gateway = FakeTargetGateway(failing=failing)

    service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSynchronizationService(
        workspace_registry,
        workspace_version_service,
        release_service,
        gateway,
    )

    return service, workspace_registry, workspace_version_service, release_service, gateway


class TestSyncSingleWorkspace:
    def test_sync_single_workspace(self):
        service, *_ = _build_service()

        result = service.sync_target("workspace-1", "registry")

        assert isinstance(result, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSyncResult)
        assert result.synchronized is True
        assert result.synchronized_targets == ("registry",)
        assert len(service.pending()) == 1

        applied = service.sync_all()

        assert applied.synchronized is True
        assert applied.synchronized_targets == ("registry",)
        assert applied.failed_targets == ()
        assert service.is_synchronized("workspace-1") is True
        assert service.pending() == ()


class TestSyncAllWorkspaces:
    def test_sync_all_workspaces(self):
        service, *_ = _build_service(workspaces=(("workspace-1", ()), ("workspace-2", ())))

        service.sync_target("workspace-1", "registry")
        service.sync_target("workspace-2", "cache")

        result = service.sync_all()

        assert result.synchronized is True
        assert result.synchronized_targets == ("registry", "cache")
        assert service.is_synchronized("workspace-1") is True
        assert service.is_synchronized("workspace-2") is True
        assert service.pending() == ()


class TestSyncSpecificTarget:
    def test_sync_specific_target(self):
        service, *_ = _build_service()

        service.sync_target("workspace-1", "registry")
        service.sync_target("workspace-1", "cache")
        service.sync_all()

        assert service.is_synchronized("workspace-1") is True

        result = service.sync("workspace-1")

        assert result.synchronized is False
        assert result.synchronized_targets == ()


class TestRetryFailedSync:
    def test_retry_failed_synchronization(self):
        service, _, _, _, gateway = _build_service(failing=(("workspace-1", "cache"),))

        service.sync_target("workspace-1", "cache")
        first_apply = service.sync_all()

        assert first_apply.synchronized is False
        assert first_apply.failed_targets == ("cache",)
        assert service.is_synchronized("workspace-1") is False

        gateway.failing.discard(("workspace-1", "cache"))

        retried = service.sync("workspace-1")

        assert retried.synchronized_targets == ("cache",)

        second_apply = service.sync_all()

        assert second_apply.synchronized is True
        assert second_apply.synchronized_targets == ("cache",)
        assert second_apply.failed_targets == ()
        assert service.is_synchronized("workspace-1") is True


class TestPendingSyncLookup:
    def test_pending_synchronization(self):
        service, *_ = _build_service()

        service.sync_target("workspace-1", "registry")

        pending = service.pending()

        assert len(pending) == 1
        assert pending[0].workspace_id == "workspace-1"
        assert pending[0].target == "registry"


class TestIdempotentSynchronization:
    def test_idempotent_when_unchanged(self):
        service, *_ = _build_service()

        service.sync_target("workspace-1", "registry")
        service.sync_all()

        second = service.sync_target("workspace-1", "registry")

        assert second.synchronized is False
        assert second.synchronized_targets == ()
        assert service.pending() == ()

    def test_reject_duplicate_pending_synchronization(self):
        service, *_ = _build_service()

        service.sync_target("workspace-1", "registry")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSyncError):
            service.sync_target("workspace-1", "registry")


class TestVersionAndReleaseAwareSync:
    def test_publishing_a_version_invalidates_prior_sync(self):
        service, workspace_registry, workspace_version_service, release_service, _ = _build_service()

        service.sync_target("workspace-1", "registry")
        service.sync_all()

        assert service.is_synchronized("workspace-1") is True

        workspace_version_service.publish("workspace-1", "1.0.0")
        release_service.release("workspace-1", "1.0.0")

        result = service.sync_target("workspace-1", "registry")

        assert result.synchronized is True
        assert result.synchronized_targets == ("registry",)


class TestInvalidRequestRejection:
    def test_reject_blank_ids(self):
        service, *_ = _build_service()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSyncError):
            service.sync_target("   ", "registry")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSyncError):
            service.sync_target("workspace-1", None)

    def test_reject_unknown_workspace(self):
        service, *_ = _build_service()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSyncError):
            service.sync_target("workspace-missing", "registry")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSyncError):
            service.sync("workspace-missing")

    def test_reject_invalid_operation(self):
        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSyncError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSyncRequest(
                workspace_id="workspace-1",
                operation="invalid",
                target="registry",
            )

    def test_reject_none_dependencies(self):
        _, workspace_registry, workspace_version_service, release_service, gateway = _build_service()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSyncError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSynchronizationService(
                None, workspace_version_service, release_service, gateway
            )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSyncError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSynchronizationService(
                workspace_registry, None, release_service, gateway
            )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSyncError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSynchronizationService(
                workspace_registry, workspace_version_service, None, gateway
            )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSyncError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSynchronizationService(
                workspace_registry, workspace_version_service, release_service, None
            )


class TestImmutableSyncResults:
    def test_immutable_result(self):
        service, *_ = _build_service()

        result = service.sync_target("workspace-1", "registry")

        with pytest.raises(AttributeError):
            result.synchronized = False
