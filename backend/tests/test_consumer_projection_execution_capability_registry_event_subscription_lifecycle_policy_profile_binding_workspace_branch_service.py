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
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranch as Branch,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchError as BranchError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchResult as BranchResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchService as BranchService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchStatus as BranchStatus,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeOperation as ChangeOperation,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetApprovalPolicy as ApprovalPolicy,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewService as ReviewService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetService as ChangeSetService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceConflictService as ConflictService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceMergeService as MergeService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRebaseService as RebaseService,
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
    policy = ApprovalPolicy(minimum_approvals=1, require_unanimous=False)
    review_service = ReviewService(change_set_service, policy)
    conflict_service = ConflictService(change_set_service, workspace_service)
    merge_service = MergeService(change_set_service, review_service, conflict_service)
    rebase_service = RebaseService(change_set_service, version_service, conflict_service)
    branch_service = BranchService(workspace_service, version_service)

    return {
        "workspace_service": workspace_service,
        "version_service": version_service,
        "change_set_service": change_set_service,
        "review_service": review_service,
        "conflict_service": conflict_service,
        "merge_service": merge_service,
        "rebase_service": rebase_service,
        "branch_service": branch_service,
    }


class TestBindingWorkspaceBranchService:
    def test_create_branch(self):
        services = _build()
        branch_service = services["branch_service"]

        result = branch_service.create("workspace-1", "feature-x")

        assert isinstance(result, BranchResult)
        assert result.successful is True
        assert isinstance(result.branch, Branch)
        assert result.branch.workspace_id == "workspace-1"
        assert result.branch.name == "feature-x"
        assert result.branch.status == BranchStatus.OPEN
        assert result.branch.base_revision is None
        assert result.branch.head_revision is None

        services["version_service"].publish("workspace-1", "v1")
        second = branch_service.create("workspace-1", "feature-y")
        assert second.branch.base_revision == "v1"
        assert second.branch.head_revision == "v1"

        with pytest.raises(BranchError):
            branch_service.create("workspace-unknown", "feature-z")

    def test_checkout_branch(self):
        services = _build()
        branch_service = services["branch_service"]

        first = branch_service.create("workspace-1", "feature-x").branch
        second = branch_service.create("workspace-1", "feature-y").branch

        checkout_result = branch_service.checkout(first.branch_id)
        assert checkout_result.successful is True
        assert checkout_result.branch.status == BranchStatus.ACTIVE
        assert branch_service.active_branch("workspace-1").branch_id == first.branch_id

        # checking out an already-active branch is a reported no-op
        repeat_result = branch_service.checkout(first.branch_id)
        assert repeat_result.successful is False
        assert repeat_result.branch.status == BranchStatus.ACTIVE

        # checking out a different branch demotes the previous one
        switch_result = branch_service.checkout(second.branch_id)
        assert switch_result.successful is True
        assert branch_service.find(first.branch_id).status == BranchStatus.OPEN
        assert branch_service.active_branch("workspace-1").branch_id == second.branch_id

        with pytest.raises(BranchError):
            branch_service.checkout("unknown-branch")

    def test_rename_branch(self):
        services = _build()
        branch_service = services["branch_service"]

        branch = branch_service.create("workspace-1", "feature-x").branch

        renamed = branch_service.rename(branch.branch_id, "feature-x-renamed")
        assert renamed.successful is True
        assert renamed.branch.name == "feature-x-renamed"
        assert branch_service.find(branch.branch_id).name == "feature-x-renamed"

        with pytest.raises(BranchError):
            branch_service.rename(branch.branch_id, "   ")

    def test_close_branch(self):
        services = _build()
        branch_service = services["branch_service"]

        branch = branch_service.create("workspace-1", "feature-x").branch

        closed = branch_service.close(branch.branch_id)
        assert closed.successful is True
        assert closed.branch.status == BranchStatus.CLOSED

        # closed branches are read-only
        with pytest.raises(BranchError):
            branch_service.checkout(branch.branch_id)

        with pytest.raises(BranchError):
            branch_service.rename(branch.branch_id, "new-name")

        with pytest.raises(BranchError):
            branch_service.close(branch.branch_id)

    def test_closing_active_branch_rejected(self):
        services = _build()
        branch_service = services["branch_service"]

        branch = branch_service.create("workspace-1", "feature-x").branch
        branch_service.checkout(branch.branch_id)

        with pytest.raises(BranchError):
            branch_service.close(branch.branch_id)

    def test_active_branch_lookup(self):
        services = _build()
        branch_service = services["branch_service"]

        assert branch_service.active_branch("workspace-1") is None

        branch = branch_service.create("workspace-1", "feature-x").branch
        assert branch_service.active_branch("workspace-1") is None

        branch_service.checkout(branch.branch_id)
        assert branch_service.active_branch("workspace-1").branch_id == branch.branch_id

        assert branch_service.active_branch("workspace-2") is None

        with pytest.raises(BranchError):
            branch_service.active_branch("workspace-unknown")

    def test_duplicate_name_rejection(self):
        services = _build()
        branch_service = services["branch_service"]

        branch_service.create("workspace-1", "feature-x")

        with pytest.raises(BranchError):
            branch_service.create("workspace-1", "feature-x")

        # same name on a different workspace is fine
        branch_service.create("workspace-2", "feature-x")

        # renaming into a taken name is also rejected
        other = branch_service.create("workspace-1", "feature-y").branch
        with pytest.raises(BranchError):
            branch_service.rename(other.branch_id, "feature-x")

    def test_list_branches(self):
        services = _build()
        branch_service = services["branch_service"]

        first = branch_service.create("workspace-1", "feature-x").branch
        second = branch_service.create("workspace-1", "feature-y").branch
        branch_service.close(second.branch_id)

        listed = branch_service.list("workspace-1")
        assert [branch.branch_id for branch in listed] == [first.branch_id, second.branch_id]

        assert branch_service.list("workspace-2") == ()

        with pytest.raises(BranchError):
            branch_service.list("   ")

    def test_integration_with_existing_workflows(self):
        services = _build()
        workspace_service = services["workspace_service"]
        version_service = services["version_service"]
        change_set_service = services["change_set_service"]
        review_service = services["review_service"]
        merge_service = services["merge_service"]
        rebase_service = services["rebase_service"]
        branch_service = services["branch_service"]

        version_service.publish("workspace-1", "v1")

        branch = branch_service.create("workspace-1", "feature-x").branch
        assert branch.base_revision == "v1"

        checkout_result = branch_service.checkout(branch.branch_id)
        assert checkout_result.branch.head_revision == "v1"

        # change sets created while the branch is active target its
        # workspace directly through the existing change set service
        change_set = change_set_service.create(branch.workspace_id, "add binding-2")
        change_set = change_set_service.add_operation(
            change_set.change_set_id, _operation("op-1", "add", "binding", "binding-2")
        )

        review = review_service.submit(change_set.change_set_id, "reviewer-a")
        review_service.approve(review.review_id)

        # merge still works normally against the branch's workspace
        merge_result = merge_service.merge([change_set.change_set_id])
        assert merge_result.successful is True

        # a new revision lands after the merge; re-checking out refreshes head
        version_service.publish("workspace-1", "v2")
        refreshed = branch_service.checkout(branch.branch_id)
        assert refreshed.branch.head_revision == "v2"

        # rebase workflow also still operates on the same workspace
        other_change_set = change_set_service.create(branch.workspace_id, "add binding-3")
        other_change_set = change_set_service.add_operation(
            other_change_set.change_set_id, _operation("op-1", "add", "binding", "binding-3")
        )
        rebase_result = rebase_service.rebase(other_change_set.change_set_id)
        assert rebase_result.successful is True

    def test_reject_blank_ids(self):
        services = _build()
        branch_service = services["branch_service"]

        with pytest.raises(BranchError):
            branch_service.create("   ", "name")

        with pytest.raises(BranchError):
            branch_service.create("workspace-1", "   ")

        with pytest.raises(BranchError):
            branch_service.checkout("   ")

        with pytest.raises(BranchError):
            branch_service.rename("   ", "name")

        with pytest.raises(BranchError):
            branch_service.close("   ")

        with pytest.raises(BranchError):
            branch_service.active_branch("   ")

        with pytest.raises(BranchError):
            branch_service.list("   ")

        with pytest.raises(BranchError):
            branch_service.find("   ")

    def test_reject_invalid_constructor_arguments(self):
        services = _build()

        with pytest.raises(BranchError):
            BranchService(None, services["version_service"])

        with pytest.raises(BranchError):
            BranchService(services["workspace_service"], None)
