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
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchProtection as BranchProtection,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchProtectionError as BranchProtectionError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchProtectionResult as BranchProtectionResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchProtectionService as BranchProtectionService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchService as BranchService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeOperation as ChangeOperation,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetApprovalPolicy as ApprovalPolicy,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewService as ReviewService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewStatus as ReviewStatus,
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


def _build():
    binding_service = BindingRegistryService()
    template_service = TemplateRegistryService()
    preset_service = PresetRegistryService()
    group_service = GroupRegistryService()

    for binding_id in ("binding-1", "binding-2", "binding-3"):
        binding_service.register(_binding(binding_id))

    workspace_service = WorkspaceService(binding_service, template_service, preset_service, group_service)
    workspace_service.create(_workspace("workspace-1", binding_ids=("binding-1",)))

    version_service = VersionService(workspace_service)
    change_set_service = ChangeSetService(workspace_service)
    policy = ApprovalPolicy(minimum_approvals=1, require_unanimous=False)
    review_service = ReviewService(change_set_service, policy)
    conflict_service = ConflictService(change_set_service, workspace_service)
    merge_service = MergeService(change_set_service, review_service, conflict_service)
    branch_service = BranchService(workspace_service, version_service)
    protection_service = BranchProtectionService(branch_service)

    branch = branch_service.create("workspace-1", "release-1").branch

    return {
        "workspace_service": workspace_service,
        "change_set_service": change_set_service,
        "review_service": review_service,
        "conflict_service": conflict_service,
        "merge_service": merge_service,
        "branch_service": branch_service,
        "protection_service": protection_service,
        "branch": branch,
    }


class TestBindingWorkspaceBranchProtectionService:
    def test_protect_unprotect_branch(self):
        services = _build()
        protection_service = services["protection_service"]
        branch = services["branch"]

        protection = protection_service.protect(branch.branch_id)

        assert isinstance(protection, BranchProtection)
        assert protection.protected is True
        assert protection.allow_direct_changes is False
        assert protection.require_review is True
        assert protection.require_clean_merge is True

        unprotected = protection_service.unprotect(branch.branch_id)
        assert unprotected.protected is False
        assert unprotected.allow_direct_changes is True
        assert unprotected.require_review is False
        assert unprotected.require_clean_merge is False

        # unprotecting an already-unprotected branch is a graceful no-op
        again = protection_service.unprotect(branch.branch_id)
        assert again.protected is False

        with pytest.raises(BranchProtectionError):
            protection_service.protect("unknown-branch")

    def test_validate_direct_edits(self):
        services = _build()
        protection_service = services["protection_service"]
        branch = services["branch"]

        protection_service.protect(branch.branch_id)

        result = protection_service.validate_operation(branch.branch_id, {"type": "direct_edit"})
        assert isinstance(result, BranchProtectionResult)
        assert result.permitted is False
        assert len(result.violations) == 1

        protection_service.protect(branch.branch_id, allow_direct_changes=True, require_review=False)
        allowed = protection_service.validate_operation(branch.branch_id, {"type": "direct_edit"})
        assert allowed.permitted is True
        assert allowed.violations == ()

        protection_service.unprotect(branch.branch_id)
        unprotected_result = protection_service.validate_operation(branch.branch_id, {"type": "direct_edit"})
        assert unprotected_result.permitted is True

    def test_validate_merge_protection(self):
        services = _build()
        protection_service = services["protection_service"]
        branch = services["branch"]

        protection_service.protect(branch.branch_id)

        missing_approval = protection_service.validate_operation(branch.branch_id, {"type": "merge"})
        assert missing_approval.permitted is False
        assert any("approved" in violation for violation in missing_approval.violations)

        approved_but_dirty = protection_service.validate_operation(
            branch.branch_id, {"type": "merge", "approved": True, "clean": False}
        )
        assert approved_but_dirty.permitted is False
        assert any("clean" in violation for violation in approved_but_dirty.violations)

        clean_and_approved = protection_service.validate_operation(
            branch.branch_id, {"type": "merge", "approved": True, "clean": True}
        )
        assert clean_and_approved.permitted is True
        assert clean_and_approved.violations == ()

        protection_service.protect(branch.branch_id, require_review=False, require_clean_merge=False)
        lenient = protection_service.validate_operation(branch.branch_id, {"type": "merge"})
        assert lenient.permitted is True

    def test_validate_merge_protection_integrates_with_review_and_merge_services(self):
        services = _build()
        protection_service = services["protection_service"]
        change_set_service = services["change_set_service"]
        review_service = services["review_service"]
        merge_service = services["merge_service"]
        branch = services["branch"]

        protection_service.protect(branch.branch_id)

        change_set = change_set_service.create(branch.workspace_id, "add binding-2")
        change_set = change_set_service.add_operation(
            change_set.change_set_id, _operation("op-1", "add", "binding", "binding-2")
        )

        # not yet reviewed: a real caller derives "approved" from the review service itself
        approved = review_service.status(change_set.change_set_id) == ReviewStatus.APPROVED
        can_merge = merge_service.can_merge([change_set.change_set_id])

        assert approved is False

        result = protection_service.validate_operation(
            branch.branch_id, {"type": "merge", "approved": approved, "clean": can_merge}
        )
        assert result.permitted is False

        review = review_service.submit(change_set.change_set_id, "reviewer-a")
        review_service.approve(review.review_id)

        approved = review_service.status(change_set.change_set_id) == ReviewStatus.APPROVED
        can_merge = merge_service.can_merge([change_set.change_set_id])

        assert approved is True

        result = protection_service.validate_operation(
            branch.branch_id,
            {
                "type": "merge",
                "approved": approved,
                "clean": can_merge,
            },
        )
        assert result.permitted is True

    def test_prevent_protected_deletion(self):
        services = _build()
        protection_service = services["protection_service"]
        branch = services["branch"]

        protection_service.protect(branch.branch_id)

        result = protection_service.validate_operation(branch.branch_id, {"type": "delete"})
        assert result.permitted is False
        assert "cannot be deleted" in result.violations[0]

        protection_service.unprotect(branch.branch_id)
        unprotected_result = protection_service.validate_operation(branch.branch_id, {"type": "delete"})
        assert unprotected_result.permitted is True

    def test_invalid_rule_rejection(self):
        services = _build()
        protection_service = services["protection_service"]
        branch = services["branch"]

        with pytest.raises(BranchProtectionError):
            protection_service.protect(branch.branch_id, allow_direct_changes=True, require_review=True)

        with pytest.raises(BranchProtectionError):
            BranchProtection(
                branch_id=branch.branch_id,
                protected=True,
                allow_direct_changes=True,
                require_review=True,
                require_clean_merge=True,
            )

        with pytest.raises(BranchProtectionError):
            BranchProtection(
                branch_id="   ",
                protected=True,
                allow_direct_changes=False,
                require_review=True,
                require_clean_merge=True,
            )

    def test_protection_status_lookup(self):
        services = _build()
        protection_service = services["protection_service"]
        branch = services["branch"]

        default_status = protection_service.status(branch.branch_id)
        assert default_status.protected is False
        assert default_status.allow_direct_changes is True

        protection_service.protect(branch.branch_id, require_clean_merge=False)
        protected_status = protection_service.status(branch.branch_id)
        assert protected_status.protected is True
        assert protected_status.require_clean_merge is False

        protection_service.unprotect(branch.branch_id)
        assert protection_service.status(branch.branch_id).protected is False

        with pytest.raises(BranchProtectionError):
            protection_service.status("unknown-branch")

    def test_reject_unauthorized_operation_type(self):
        services = _build()
        protection_service = services["protection_service"]
        branch = services["branch"]

        with pytest.raises(BranchProtectionError):
            protection_service.validate_operation(branch.branch_id, {"type": "teleport"})

        with pytest.raises(BranchProtectionError):
            protection_service.validate_operation(branch.branch_id, {})

        with pytest.raises(BranchProtectionError):
            protection_service.validate_operation(branch.branch_id, None)

        with pytest.raises(BranchProtectionError):
            protection_service.validate_operation(branch.branch_id, "merge")

    def test_reject_blank_ids(self):
        services = _build()
        protection_service = services["protection_service"]

        with pytest.raises(BranchProtectionError):
            protection_service.protect("   ")

        with pytest.raises(BranchProtectionError):
            protection_service.unprotect("   ")

        with pytest.raises(BranchProtectionError):
            protection_service.status("   ")

        with pytest.raises(BranchProtectionError):
            protection_service.validate_operation("   ", {"type": "delete"})

    def test_reject_unknown_branch(self):
        services = _build()
        protection_service = services["protection_service"]

        with pytest.raises(BranchProtectionError):
            protection_service.unprotect("unknown-branch")

        with pytest.raises(BranchProtectionError):
            protection_service.status("unknown-branch")

        with pytest.raises(BranchProtectionError):
            protection_service.validate_operation("unknown-branch", {"type": "delete"})

    def test_reject_invalid_constructor_arguments(self):
        with pytest.raises(BranchProtectionError):
            BranchProtectionService(None)
