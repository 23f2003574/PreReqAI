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
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchComparison as BranchComparison,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchComparisonError as BranchComparisonError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchComparisonService as BranchComparisonService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchService as BranchService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeOperation as ChangeOperation,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetApprovalPolicy as ApprovalPolicy,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewService as ReviewService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetService as ChangeSetService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceConflictService as ConflictService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceMergeService as MergeService,
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


def _build(workspace_1_bindings=("binding-1",), workspace_2_bindings=("binding-2",)):
    binding_service = BindingRegistryService()
    template_service = TemplateRegistryService()
    preset_service = PresetRegistryService()
    group_service = GroupRegistryService()

    for binding_id in ("binding-1", "binding-2", "binding-3", "binding-4"):
        binding_service.register(_binding(binding_id))

    workspace_service = WorkspaceService(binding_service, template_service, preset_service, group_service)
    workspace_service.create(_workspace("workspace-1", binding_ids=workspace_1_bindings))
    workspace_service.create(_workspace("workspace-2", binding_ids=workspace_2_bindings))

    version_service = VersionService(workspace_service)
    change_set_service = ChangeSetService(workspace_service)
    policy = ApprovalPolicy(minimum_approvals=1, require_unanimous=False)
    review_service = ReviewService(change_set_service, policy)
    conflict_service = ConflictService(change_set_service, workspace_service)
    merge_service = MergeService(change_set_service, review_service, conflict_service)
    branch_service = BranchService(workspace_service, version_service)
    comparison_service = BranchComparisonService(branch_service, workspace_service, change_set_service)

    branch_a = branch_service.create("workspace-1", "branch-a").branch
    branch_b = branch_service.create("workspace-2", "branch-b").branch

    return {
        "workspace_service": workspace_service,
        "change_set_service": change_set_service,
        "review_service": review_service,
        "merge_service": merge_service,
        "branch_service": branch_service,
        "comparison_service": comparison_service,
        "branch_a": branch_a,
        "branch_b": branch_b,
    }


class TestBindingWorkspaceBranchComparisonService:
    def test_compare_branches(self):
        services = _build()
        comparison_service = services["comparison_service"]
        branch_a = services["branch_a"]
        branch_b = services["branch_b"]

        comparison = comparison_service.compare(branch_a.branch_id, branch_b.branch_id)

        assert isinstance(comparison, BranchComparison)
        assert comparison.source_branch.branch_id == branch_a.branch_id
        assert comparison.target_branch.branch_id == branch_b.branch_id

        with pytest.raises(BranchComparisonError):
            comparison_service.compare("unknown-branch", branch_b.branch_id)

        with pytest.raises(BranchComparisonError):
            comparison_service.compare(branch_a.branch_id, "unknown-branch")

    def test_detect_differences(self):
        services = _build(workspace_1_bindings=("binding-1",), workspace_2_bindings=("binding-2",))
        comparison_service = services["comparison_service"]
        branch_a = services["branch_a"]
        branch_b = services["branch_b"]

        comparison = comparison_service.compare(branch_a.branch_id, branch_b.branch_id)

        differences = {(d.resource_type, d.resource_id): d.change_type for d in comparison.differences}

        assert differences[("binding", "binding-1")] == "addition"
        assert differences[("binding", "binding-2")] == "deletion"
        assert len(comparison.differences) == 2

        summary = comparison_service.summary(comparison.comparison_id)
        assert summary["addition"] == 1
        assert summary["deletion"] == 1
        assert summary["update"] == 0
        assert summary["total"] == 2

    def test_identical_branch_comparison(self):
        services = _build()
        comparison_service = services["comparison_service"]
        branch_a = services["branch_a"]

        with pytest.raises(BranchComparisonError):
            comparison_service.compare(branch_a.branch_id, branch_a.branch_id)

        with pytest.raises(BranchComparisonError):
            BranchComparison(
                comparison_id="comparison-1",
                source_branch=branch_a,
                target_branch=branch_a,
                differences=(),
            )

    def test_conflict_detection(self):
        services = _build(workspace_1_bindings=("binding-1",), workspace_2_bindings=("binding-1",))
        comparison_service = services["comparison_service"]
        change_set_service = services["change_set_service"]
        branch_a = services["branch_a"]
        branch_b = services["branch_b"]

        # both workspaces currently share binding-1; workspace-1 stages a
        # redundant add against it, so its fate is actively "in flux"
        change_set = change_set_service.create("workspace-1", "touch binding-1")
        change_set_service.add_operation(
            change_set.change_set_id, _operation("op-1", "add", "binding", "binding-1")
        )

        comparison = comparison_service.compare(branch_a.branch_id, branch_b.branch_id)

        assert comparison_service.has_conflicts(comparison.comparison_id) is True
        assert len(comparison.differences) == 1
        assert comparison.differences[0].change_type == "update"
        assert comparison.differences[0].resource_id == "binding-1"

        clean_comparison = comparison_service.compare(branch_b.branch_id, branch_a.branch_id)
        # comparing in the other direction is still the same underlying divergence
        assert comparison_service.has_conflicts(clean_comparison.comparison_id) is True

    def test_no_conflicts_when_states_agree(self):
        services = _build(workspace_1_bindings=("binding-1",), workspace_2_bindings=("binding-1",))
        comparison_service = services["comparison_service"]
        branch_a = services["branch_a"]
        branch_b = services["branch_b"]

        comparison = comparison_service.compare(branch_a.branch_id, branch_b.branch_id)

        assert comparison.differences == ()
        assert comparison_service.has_conflicts(comparison.comparison_id) is False

    def test_export_comparison(self):
        services = _build(workspace_1_bindings=("binding-1",), workspace_2_bindings=("binding-2",))
        comparison_service = services["comparison_service"]
        branch_a = services["branch_a"]
        branch_b = services["branch_b"]

        comparison = comparison_service.compare(branch_a.branch_id, branch_b.branch_id)
        exported = comparison_service.export(comparison.comparison_id)

        assert exported["comparison_id"] == comparison.comparison_id
        assert exported["source_branch_id"] == branch_a.branch_id
        assert exported["target_branch_id"] == branch_b.branch_id
        assert len(exported["differences"]) == 2
        assert all(
            set(entry.keys()) == {"resource_type", "resource_id", "change_type"}
            for entry in exported["differences"]
        )

        with pytest.raises(BranchComparisonError):
            comparison_service.export("unknown-comparison")

    def test_integration_with_merge_preview(self):
        services = _build(workspace_1_bindings=(), workspace_2_bindings=())
        comparison_service = services["comparison_service"]
        change_set_service = services["change_set_service"]
        review_service = services["review_service"]
        merge_service = services["merge_service"]
        branch_a = services["branch_a"]
        branch_b = services["branch_b"]

        change_set = change_set_service.create("workspace-1", "add binding-4")
        change_set = change_set_service.add_operation(
            change_set.change_set_id, _operation("op-1", "add", "binding", "binding-4")
        )

        comparison = comparison_service.compare(branch_a.branch_id, branch_b.branch_id)
        assert len(comparison.differences) == 1
        assert comparison.differences[0].resource_id == "binding-4"
        assert comparison.differences[0].change_type == "addition"

        review = review_service.submit(change_set.change_set_id, "reviewer-a")
        review_service.approve(review.review_id)

        preview = merge_service.preview_merge([change_set.change_set_id])
        assert preview.successful is True
        assert [operation.resource_id for operation in preview.merged_operations] == ["binding-4"]

    def test_reject_blank_ids(self):
        services = _build()
        comparison_service = services["comparison_service"]
        branch_a = services["branch_a"]
        branch_b = services["branch_b"]

        with pytest.raises(BranchComparisonError):
            comparison_service.compare("   ", branch_b.branch_id)

        with pytest.raises(BranchComparisonError):
            comparison_service.compare(branch_a.branch_id, "   ")

        with pytest.raises(BranchComparisonError):
            comparison_service.summary("   ")

        with pytest.raises(BranchComparisonError):
            comparison_service.has_conflicts("   ")

        with pytest.raises(BranchComparisonError):
            comparison_service.export("   ")

        with pytest.raises(BranchComparisonError):
            comparison_service.find("   ")

    def test_reject_unknown_comparison(self):
        services = _build()
        comparison_service = services["comparison_service"]

        with pytest.raises(BranchComparisonError):
            comparison_service.summary("unknown-comparison")

        with pytest.raises(BranchComparisonError):
            comparison_service.has_conflicts("unknown-comparison")

        assert comparison_service.find("unknown-comparison") is None

    def test_reject_invalid_constructor_arguments(self):
        services = _build()

        with pytest.raises(BranchComparisonError):
            BranchComparisonService(None, services["workspace_service"], services["change_set_service"])

        with pytest.raises(BranchComparisonError):
            BranchComparisonService(services["branch_service"], None, services["change_set_service"])

        with pytest.raises(BranchComparisonError):
            BranchComparisonService(services["branch_service"], services["workspace_service"], None)
