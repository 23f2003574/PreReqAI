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
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchArchive as BranchArchive,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchArchiveError as BranchArchiveError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchArchiveService as BranchArchiveService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchRecoveryResult as BranchRecoveryResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchService as BranchService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchStatus as BranchStatus,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetService as ChangeSetService,
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


def _build():
    binding_service = BindingRegistryService()
    template_service = TemplateRegistryService()
    preset_service = PresetRegistryService()
    group_service = GroupRegistryService()

    for binding_id in ("binding-1",):
        binding_service.register(_binding(binding_id))

    workspace_service = WorkspaceService(binding_service, template_service, preset_service, group_service)
    workspace_service.create(_workspace("workspace-1", binding_ids=("binding-1",)))
    workspace_service.create(_workspace("workspace-2", binding_ids=()))

    version_service = VersionService(workspace_service)
    change_set_service = ChangeSetService(workspace_service)
    branch_service = BranchService(workspace_service, version_service)
    archive_service = BranchArchiveService(branch_service)

    return {
        "workspace_service": workspace_service,
        "version_service": version_service,
        "change_set_service": change_set_service,
        "branch_service": branch_service,
        "archive_service": archive_service,
    }


class TestBindingWorkspaceBranchArchiveService:
    def test_archive_branch(self):
        services = _build()
        branch_service = services["branch_service"]
        archive_service = services["archive_service"]

        branch = branch_service.create("workspace-1", "feature-x").branch

        record = archive_service.archive(branch.branch_id, reason="feature shipped")

        assert isinstance(record, BranchArchive)
        assert record.branch_id == branch.branch_id
        assert record.reason == "feature shipped"
        assert record.archived_at is not None

        assert archive_service.is_archived(branch.branch_id) is True

        with pytest.raises(BranchArchiveError):
            archive_service.archive("unknown-branch")

    def test_restore_branch(self):
        services = _build()
        branch_service = services["branch_service"]
        archive_service = services["archive_service"]

        branch = branch_service.create("workspace-1", "feature-x").branch
        archive_service.archive(branch.branch_id)

        result = archive_service.restore(branch.branch_id)

        assert isinstance(result, BranchRecoveryResult)
        assert result.branch_id == branch.branch_id
        assert result.recovered is True
        assert result.recovered_at is not None

        assert archive_service.is_archived(branch.branch_id) is False

    def test_resume_from_archived_revision(self):
        services = _build()
        version_service = services["version_service"]
        branch_service = services["branch_service"]
        archive_service = services["archive_service"]

        version_service.publish("workspace-1", "v1")
        branch = branch_service.create("workspace-1", "feature-x").branch
        assert branch.base_revision == "v1"

        archive_service.archive(branch.branch_id)

        # unrelated workspace activity happens while the branch is archived
        version_service.publish("workspace-1", "v2")

        archive_service.restore(branch.branch_id)

        # archiving never touched the branch: it resumes exactly as it was
        restored_branch = branch_service.find(branch.branch_id)
        assert restored_branch.base_revision == "v1"
        assert restored_branch.head_revision == "v1"
        assert restored_branch.status == BranchStatus.OPEN
        assert restored_branch.name == "feature-x"

    def test_archive_lookup(self):
        services = _build()
        branch_service = services["branch_service"]
        archive_service = services["archive_service"]

        branch = branch_service.create("workspace-1", "feature-x").branch

        assert archive_service.is_archived(branch.branch_id) is False

        archive_service.archive(branch.branch_id)
        assert archive_service.is_archived(branch.branch_id) is True

        with pytest.raises(BranchArchiveError):
            archive_service.is_archived("unknown-branch")

        with pytest.raises(BranchArchiveError):
            archive_service.is_archived("   ")

    def test_archived_branch_excluded_from_listings(self):
        services = _build()
        branch_service = services["branch_service"]
        archive_service = services["archive_service"]

        first = branch_service.create("workspace-1", "feature-x").branch
        second = branch_service.create("workspace-1", "feature-y").branch

        archive_service.archive(first.branch_id)
        archive_service.archive(second.branch_id)

        active_archives = archive_service.archives("workspace-1")
        assert {record.branch_id for record in active_archives} == {first.branch_id, second.branch_id}

        # restoring removes it from the current archive listing...
        archive_service.restore(first.branch_id)
        remaining = archive_service.archives("workspace-1")
        assert {record.branch_id for record in remaining} == {second.branch_id}

        # ...but branch_service.list() itself is entirely unaffected by archiving
        assert {branch.branch_id for branch in branch_service.list("workspace-1")} == {
            first.branch_id,
            second.branch_id,
        }

    def test_history_preserved(self):
        services = _build()
        branch_service = services["branch_service"]
        archive_service = services["archive_service"]

        branch = branch_service.create("workspace-1", "feature-x").branch

        first_archive = archive_service.archive(branch.branch_id, reason="pausing work")
        archive_service.restore(branch.branch_id)
        second_archive = archive_service.archive(branch.branch_id, reason="shipped")

        history = archive_service.history(branch.branch_id)

        assert [record.archive_id for record in history] == [
            first_archive.archive_id,
            second_archive.archive_id,
        ]

        # the current archive listing only reflects the branch's current state
        assert archive_service.is_archived(branch.branch_id) is True
        assert archive_service.find(first_archive.archive_id) == first_archive

    def test_invalid_archive_and_recovery(self):
        services = _build()
        branch_service = services["branch_service"]
        archive_service = services["archive_service"]

        active_branch = branch_service.create("workspace-1", "active-feature").branch
        branch_service.checkout(active_branch.branch_id)

        with pytest.raises(BranchArchiveError):
            archive_service.archive(active_branch.branch_id)

        open_branch = branch_service.create("workspace-1", "open-feature").branch

        with pytest.raises(BranchArchiveError):
            archive_service.restore(open_branch.branch_id)

        archive_service.archive(open_branch.branch_id)

        with pytest.raises(BranchArchiveError):
            archive_service.archive(open_branch.branch_id)

    def test_excluded_from_active_workflows(self):
        services = _build()
        branch_service = services["branch_service"]
        archive_service = services["archive_service"]
        change_set_service = services["change_set_service"]

        def _create_change_set_for_branch(branch):
            # this is exactly the guard a real workflow integration would
            # add in front of an existing, unmodified change_set_service
            # call: consult is_archived() and refuse to proceed
            if archive_service.is_archived(branch.branch_id):
                raise BranchArchiveError(
                    f"Cannot create a change set: branch ID {branch.branch_id!r} is archived."
                )

            return change_set_service.create(branch.workspace_id, "guarded creation")

        active_branch = branch_service.create("workspace-1", "feature-x").branch
        created = _create_change_set_for_branch(active_branch)
        assert created is not None

        archive_service.archive(active_branch.branch_id)

        with pytest.raises(BranchArchiveError):
            _create_change_set_for_branch(active_branch)

    def test_reject_blank_ids(self):
        services = _build()
        archive_service = services["archive_service"]

        with pytest.raises(BranchArchiveError):
            archive_service.archive("   ")

        with pytest.raises(BranchArchiveError):
            archive_service.restore("   ")

        with pytest.raises(BranchArchiveError):
            archive_service.archives("   ")

        with pytest.raises(BranchArchiveError):
            archive_service.is_archived("   ")

        with pytest.raises(BranchArchiveError):
            archive_service.history("   ")

        with pytest.raises(BranchArchiveError):
            archive_service.find("   ")

    def test_reject_unknown_branch_and_workspace(self):
        services = _build()
        archive_service = services["archive_service"]

        with pytest.raises(BranchArchiveError):
            archive_service.restore("unknown-branch")

        with pytest.raises(BranchArchiveError):
            archive_service.history("unknown-branch")

        with pytest.raises(BranchArchiveError):
            archive_service.archives("unknown-workspace")

        assert archive_service.find("unknown-archive") is None

    def test_reject_invalid_model_arguments(self):
        with pytest.raises(BranchArchiveError):
            BranchArchive(
                archive_id="   ",
                branch_id="branch-1",
                archived_at=datetime.now(timezone.utc),
                reason=None,
            )

        with pytest.raises(BranchArchiveError):
            BranchArchive(
                archive_id="archive-1",
                branch_id="branch-1",
                archived_at=datetime.now(timezone.utc),
                reason="   ",
            )

        with pytest.raises(BranchArchiveError):
            BranchRecoveryResult(branch_id="branch-1", recovered=True, recovered_at=None)

        with pytest.raises(BranchArchiveError):
            BranchRecoveryResult(
                branch_id="branch-1", recovered=False, recovered_at=datetime.now(timezone.utc)
            )

    def test_reject_invalid_constructor_arguments(self):
        with pytest.raises(BranchArchiveError):
            BranchArchiveService(None)
