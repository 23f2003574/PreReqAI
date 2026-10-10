from datetime import (
    datetime,
    timezone,
)

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBinding as Binding,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryService as GroupRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryService as PresetRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryService as BindingRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryService as TemplateRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspace as Workspace,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchService as BranchService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchSync as BranchSync,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchSyncError as BranchSyncError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchSyncResult as BranchSyncResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchSyncStatus as BranchSyncStatus,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchSynchronizationService as BranchSynchronizationService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeOperation as ChangeOperation,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetService as ChangeSetService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceConflictService as ConflictService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceService as WorkspaceService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionService as VersionService,
)


def _binding(binding_id):
    return Binding(
        binding_id=binding_id,
        profile_id="development",
        capability_id="capability-a",
        created_at=datetime.now(timezone.utc),
    )


def _workspace(workspace_id, binding_ids=()):
    return Workspace(
        workspace_id=workspace_id,
        name=workspace_id,
        description="A workspace.",
        binding_ids=binding_ids,
        template_ids=(),
        preset_ids=(),
        group_ids=(),
    )


def _operation(operation_id, operation_type, resource_type, resource_id):
    return ChangeOperation(
        operation_id=operation_id,
        operation_type=operation_type,
        resource_type=resource_type,
        resource_id=resource_id,
    )


def _build():
    binding_service = BindingRegistryService()
    template_service = TemplateRegistryService()
    preset_service = PresetRegistryService()
    group_service = GroupRegistryService()

    for binding_id in ("binding-1", "binding-2", "binding-3"):
        binding_service.register(_binding(binding_id))

    workspace_service = WorkspaceService(binding_service, template_service, preset_service, group_service)
    workspace_service.create(_workspace("workspace-1", binding_ids=("binding-1",)))
    workspace_service.create(_workspace("workspace-2", binding_ids=()))

    version_service = VersionService(workspace_service)
    change_set_service = ChangeSetService(workspace_service)
    conflict_service = ConflictService(change_set_service, workspace_service)
    branch_service = BranchService(workspace_service, version_service)
    sync_service = BranchSynchronizationService(
        branch_service, change_set_service, version_service, conflict_service
    )

    return {
        "workspace_service": workspace_service,
        "version_service": version_service,
        "change_set_service": change_set_service,
        "conflict_service": conflict_service,
        "branch_service": branch_service,
        "sync_service": sync_service,
    }


class TestBindingWorkspaceBranchSynchronizationService:
    def test_successful_sync(self):
        services = _build()
        version_service = services["version_service"]
        branch_service = services["branch_service"]
        sync_service = services["sync_service"]

        version_service.publish("workspace-1", "v1")
        branch = branch_service.create("workspace-1", "feature-x").branch
        assert branch.base_revision == "v1"

        version_service.publish("workspace-1", "v2")

        result = sync_service.sync(branch.branch_id)

        assert isinstance(result, BranchSyncResult)
        assert result.synchronized is True
        assert result.conflicts == ()
        assert result.synchronized_at is not None

        history = sync_service.sync_history(branch.branch_id)
        assert len(history) == 1
        assert isinstance(history[0], BranchSync)
        assert history[0].source_revision == "v1"
        assert history[0].target_revision == "v2"
        assert history[0].status == BranchSyncStatus.SUCCEEDED

    def test_preview_sync(self):
        services = _build()
        version_service = services["version_service"]
        branch_service = services["branch_service"]
        sync_service = services["sync_service"]

        version_service.publish("workspace-1", "v1")
        branch = branch_service.create("workspace-1", "feature-x").branch
        version_service.publish("workspace-1", "v2")

        preview = sync_service.preview_sync(branch.branch_id)

        assert preview.synchronized is True
        assert preview.conflicts == ()
        assert preview.synchronized_at is None

        # preview must not advance tracked revision or record history
        assert sync_service.sync_history(branch.branch_id) == ()
        assert sync_service.can_sync(branch.branch_id) is True

    def test_already_synchronized(self):
        services = _build()
        version_service = services["version_service"]
        branch_service = services["branch_service"]
        sync_service = services["sync_service"]

        version_service.publish("workspace-1", "v1")
        branch = branch_service.create("workspace-1", "feature-x").branch

        # nothing has changed since the branch was created
        assert sync_service.can_sync(branch.branch_id) is False

        with pytest.raises(BranchSyncError):
            sync_service.sync(branch.branch_id)

        with pytest.raises(BranchSyncError):
            sync_service.preview_sync(branch.branch_id)

        version_service.publish("workspace-1", "v2")
        sync_service.sync(branch.branch_id)

        # now up to date again, until the next publish
        assert sync_service.can_sync(branch.branch_id) is False
        with pytest.raises(BranchSyncError):
            sync_service.sync(branch.branch_id)

    def test_sync_with_conflicts(self):
        services = _build()
        version_service = services["version_service"]
        branch_service = services["branch_service"]
        sync_service = services["sync_service"]
        change_set_service = services["change_set_service"]

        version_service.publish("workspace-1", "v1")
        branch = branch_service.create("workspace-1", "feature-x").branch

        # binding-1 is already a member of workspace-1, so this operation is stale
        change_set = change_set_service.create("workspace-1", "stale add")
        change_set_service.add_operation(
            change_set.change_set_id, _operation("op-1", "add", "binding", "binding-1")
        )

        version_service.publish("workspace-1", "v2")

        result = sync_service.sync(branch.branch_id)

        assert result.synchronized is False
        assert result.synchronized_at is None
        assert len(result.conflicts) >= 1
        assert all(conflict.conflict_type == "stale_state" for conflict in result.conflicts)

        history = sync_service.sync_history(branch.branch_id)
        assert len(history) == 1
        assert history[0].status == BranchSyncStatus.FAILED

        # blocked sync leaves the branch eligible to retry
        assert sync_service.can_sync(branch.branch_id) is False  # still blocked by the same conflict

    def test_sync_history(self):
        services = _build()
        version_service = services["version_service"]
        branch_service = services["branch_service"]
        sync_service = services["sync_service"]

        version_service.publish("workspace-1", "v1")
        branch = branch_service.create("workspace-1", "feature-x").branch

        version_service.publish("workspace-1", "v2")
        sync_service.sync(branch.branch_id)

        version_service.publish("workspace-1", "v3")
        sync_service.sync(branch.branch_id)

        history = sync_service.sync_history(branch.branch_id)
        assert len(history) == 2
        assert history[0].target_revision == "v2"
        assert history[1].target_revision == "v3"
        assert history[1].source_revision == "v2"

        other_branch = branch_service.create("workspace-1", "feature-y").branch
        assert sync_service.sync_history(other_branch.branch_id) == ()

        with pytest.raises(BranchSyncError):
            sync_service.sync_history("   ")

    def test_invalid_request_rejection(self):
        services = _build()
        branch_service = services["branch_service"]
        sync_service = services["sync_service"]
        version_service = services["version_service"]

        with pytest.raises(BranchSyncError):
            sync_service.sync("   ")

        with pytest.raises(BranchSyncError):
            sync_service.sync("unknown-branch")

        with pytest.raises(BranchSyncError):
            sync_service.preview_sync("   ")

        with pytest.raises(BranchSyncError):
            sync_service.can_sync("   ")

        with pytest.raises(BranchSyncError):
            sync_service.find("   ")

        version_service.publish("workspace-1", "v1")
        branch = branch_service.create("workspace-1", "feature-x").branch
        branch_service.checkout(branch.branch_id)
        branch_service.checkout(branch_service.create("workspace-1", "feature-y").branch.branch_id)
        branch_service.close(branch.branch_id)

        with pytest.raises(BranchSyncError):
            sync_service.sync(branch.branch_id)

        assert sync_service.can_sync(branch.branch_id) is False

        with pytest.raises(BranchSyncError):
            BranchSynchronizationService(None, services["change_set_service"], version_service, services["conflict_service"])

        with pytest.raises(BranchSyncError):
            BranchSynchronizationService(branch_service, None, version_service, services["conflict_service"])

        with pytest.raises(BranchSyncError):
            BranchSynchronizationService(branch_service, services["change_set_service"], None, services["conflict_service"])

        with pytest.raises(BranchSyncError):
            BranchSynchronizationService(branch_service, services["change_set_service"], version_service, None)

    def test_no_revision_published_treated_as_already_synchronized(self):
        services = _build()
        branch_service = services["branch_service"]
        sync_service = services["sync_service"]

        branch = branch_service.create("workspace-1", "feature-x").branch
        assert branch.base_revision is None

        with pytest.raises(BranchSyncError):
            sync_service.sync(branch.branch_id)

        assert sync_service.can_sync(branch.branch_id) is False
