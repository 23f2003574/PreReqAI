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
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchProtectionService as ProtectionService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchService as BranchService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchSynchronizationService as BranchSynchronizationService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchTemplate as BranchTemplate,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchTemplateAssignment as BranchTemplateAssignment,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchTemplateError as BranchTemplateError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchTemplateService as BranchTemplateService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetApprovalPolicy as ApprovalPolicy,
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


def _protection_policy(allow_direct_changes=False, require_review=True, require_clean_merge=True):
    return {
        "allow_direct_changes": allow_direct_changes,
        "require_review": require_review,
        "require_clean_merge": require_clean_merge,
    }


def _sync_policy(auto_sync=False, stale_threshold_days=14):
    return {"auto_sync": auto_sync, "stale_threshold_days": stale_threshold_days}


def _template(template_id, name, **overrides):
    return BranchTemplate(
        template_id=template_id,
        name=name,
        protection_policy=overrides.get("protection_policy", _protection_policy()),
        review_policy=overrides.get("review_policy", ApprovalPolicy(minimum_approvals=1, require_unanimous=False)),
        sync_policy=overrides.get("sync_policy", _sync_policy()),
    )


def _build():
    binding_service = BindingRegistryService()
    template_reg_service = TemplateRegistryService()
    preset_service = PresetRegistryService()
    group_service = GroupRegistryService()

    for binding_id in ("binding-1",):
        binding_service.register(_binding(binding_id))

    workspace_service = WorkspaceService(binding_service, template_reg_service, preset_service, group_service)
    workspace_service.create(_workspace("workspace-1", binding_ids=("binding-1",)))

    version_service = VersionService(workspace_service)
    change_set_service = ChangeSetService(workspace_service)
    conflict_service = ConflictService(change_set_service, workspace_service)
    branch_service = BranchService(workspace_service, version_service)
    protection_service = ProtectionService(branch_service)
    sync_service = BranchSynchronizationService(
        branch_service, change_set_service, version_service, conflict_service
    )
    branch_template_service = BranchTemplateService(branch_service, protection_service, sync_service)

    return {
        "workspace_service": workspace_service,
        "version_service": version_service,
        "change_set_service": change_set_service,
        "branch_service": branch_service,
        "protection_service": protection_service,
        "sync_service": sync_service,
        "branch_template_service": branch_template_service,
    }


class TestBindingWorkspaceBranchTemplateService:
    def test_register_template(self):
        services = _build()
        template_service = services["branch_template_service"]

        template = _template("template-1", "strict-review")
        registered = template_service.register(template)

        assert registered == template
        assert template_service.find("template-1") == template
        assert template_service.list() == (template,)

        with pytest.raises(BranchTemplateError):
            template_service.register(None)

        with pytest.raises(BranchTemplateError):
            template_service.register("not-a-template")

    def test_assign_unassign_template(self):
        services = _build()
        branch_service = services["branch_service"]
        protection_service = services["protection_service"]
        template_service = services["branch_template_service"]

        branch = branch_service.create("workspace-1", "feature-x").branch
        template = template_service.register(_template("template-1", "strict-review"))

        assignment = template_service.assign(branch.branch_id, template.template_id)

        assert isinstance(assignment, BranchTemplateAssignment)
        assert assignment.branch_id == branch.branch_id
        assert assignment.template_id == template.template_id
        assert assignment.assigned_at is not None

        assert template_service.template(branch.branch_id) == template

        removed = template_service.unassign(branch.branch_id)
        assert removed == assignment
        assert template_service.template(branch.branch_id) is None
        assert protection_service.status(branch.branch_id).protected is False

    def test_policy_application(self):
        services = _build()
        branch_service = services["branch_service"]
        protection_service = services["protection_service"]
        template_service = services["branch_template_service"]

        branch = branch_service.create("workspace-1", "feature-x").branch
        template = template_service.register(
            _template(
                "template-1",
                "lenient",
                protection_policy=_protection_policy(
                    allow_direct_changes=False, require_review=True, require_clean_merge=False
                ),
            )
        )

        template_service.assign(branch.branch_id, template.template_id)

        status = protection_service.status(branch.branch_id)
        assert status.protected is True
        assert status.allow_direct_changes is False
        assert status.require_review is True
        assert status.require_clean_merge is False

    def test_policy_application_triggers_auto_sync(self):
        services = _build()
        version_service = services["version_service"]
        branch_service = services["branch_service"]
        sync_service = services["sync_service"]
        template_service = services["branch_template_service"]

        version_service.publish("workspace-1", "v1")
        branch = branch_service.create("workspace-1", "feature-x").branch
        version_service.publish("workspace-1", "v2")

        template = template_service.register(
            _template("template-1", "auto-sync", sync_policy=_sync_policy(auto_sync=True))
        )

        template_service.assign(branch.branch_id, template.template_id)

        history = sync_service.sync_history(branch.branch_id)
        assert len(history) == 1
        assert history[0].target_revision == "v2"

    def test_duplicate_template_rejection(self):
        services = _build()
        template_service = services["branch_template_service"]

        template_service.register(_template("template-1", "strict-review"))

        with pytest.raises(BranchTemplateError):
            template_service.register(_template("template-2", "strict-review"))

        with pytest.raises(BranchTemplateError):
            template_service.register(_template("template-1", "different-name"))

    def test_invalid_assignment(self):
        services = _build()
        branch_service = services["branch_service"]
        template_service = services["branch_template_service"]

        branch = branch_service.create("workspace-1", "feature-x").branch
        first = template_service.register(_template("template-1", "first"))
        second = template_service.register(_template("template-2", "second"))

        with pytest.raises(BranchTemplateError):
            template_service.assign("unknown-branch", first.template_id)

        with pytest.raises(BranchTemplateError):
            template_service.assign(branch.branch_id, "unknown-template")

        template_service.assign(branch.branch_id, first.template_id)

        # assigning multiple templates simultaneously is rejected
        with pytest.raises(BranchTemplateError):
            template_service.assign(branch.branch_id, second.template_id)

        with pytest.raises(BranchTemplateError):
            template_service.unassign("unknown-branch")

        other_branch = branch_service.create("workspace-1", "no-template").branch
        with pytest.raises(BranchTemplateError):
            template_service.unassign(other_branch.branch_id)

    def test_branch_history_unaffected(self):
        services = _build()
        workspace_service = services["workspace_service"]
        version_service = services["version_service"]
        branch_service = services["branch_service"]
        template_service = services["branch_template_service"]

        version_service.publish("workspace-1", "v1")
        branch = branch_service.create("workspace-1", "feature-x").branch

        before = branch_service.find(branch.branch_id)

        template = template_service.register(_template("template-1", "strict-review"))
        template_service.assign(branch.branch_id, template.template_id)
        template_service.unassign(branch.branch_id)

        after = branch_service.find(branch.branch_id)

        assert after.name == before.name
        assert after.workspace_id == before.workspace_id
        assert after.base_revision == before.base_revision
        assert after.head_revision == before.head_revision
        assert after.status == before.status
        assert branch_service.list("workspace-1") == (branch,)

    def test_reject_blank_ids(self):
        services = _build()
        template_service = services["branch_template_service"]

        with pytest.raises(BranchTemplateError):
            template_service.assign("   ", "template-1")

        with pytest.raises(BranchTemplateError):
            template_service.assign("branch-1", "   ")

        with pytest.raises(BranchTemplateError):
            template_service.unassign("   ")

        with pytest.raises(BranchTemplateError):
            template_service.template("   ")

        with pytest.raises(BranchTemplateError):
            template_service.find("   ")

    def test_reject_invalid_model_arguments(self):
        with pytest.raises(BranchTemplateError):
            _template(
                "template-1",
                "conflicting",
                protection_policy=_protection_policy(allow_direct_changes=True, require_review=True),
            )

        with pytest.raises(BranchTemplateError):
            BranchTemplate(
                template_id="template-1",
                name="missing-key",
                protection_policy={"allow_direct_changes": False, "require_review": True},
                review_policy=ApprovalPolicy(minimum_approvals=1, require_unanimous=False),
                sync_policy=_sync_policy(),
            )

        with pytest.raises(BranchTemplateError):
            BranchTemplate(
                template_id="template-1",
                name="bad-review-policy",
                protection_policy=_protection_policy(),
                review_policy="not-a-policy",
                sync_policy=_sync_policy(),
            )

        with pytest.raises(BranchTemplateError):
            BranchTemplate(
                template_id="template-1",
                name="bad-sync-policy",
                protection_policy=_protection_policy(),
                review_policy=ApprovalPolicy(minimum_approvals=1, require_unanimous=False),
                sync_policy={"auto_sync": True, "stale_threshold_days": -1},
            )

        with pytest.raises(BranchTemplateError):
            BranchTemplateAssignment(branch_id="   ", template_id="template-1", assigned_at=datetime.now(timezone.utc))

    def test_reject_invalid_constructor_arguments(self):
        services = _build()

        with pytest.raises(BranchTemplateError):
            BranchTemplateService(None, services["protection_service"], services["sync_service"])

        with pytest.raises(BranchTemplateError):
            BranchTemplateService(services["branch_service"], None, services["sync_service"])

        with pytest.raises(BranchTemplateError):
            BranchTemplateService(services["branch_service"], services["protection_service"], None)
