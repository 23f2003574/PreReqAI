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
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeOperation as ChangeOperation,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetRebase as ChangeSetRebase,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetRebaseStatus as RebaseStatus,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetService as ChangeSetService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceConflictService as ConflictService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRebaseError as RebaseError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRebaseResult as RebaseResult,
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

    change_set_service = ChangeSetService(workspace_service)
    conflict_service = ConflictService(change_set_service, workspace_service)
    version_service = VersionService(workspace_service)
    rebase_service = RebaseService(change_set_service, version_service, conflict_service)

    return workspace_service, change_set_service, conflict_service, version_service, rebase_service


class TestBindingWorkspaceRebaseService:
    def test_successful_rebase(self):
        workspace_service, change_set_service, conflict_service, version_service, rebase_service = _build()

        version_service.publish("workspace-1", "v1")

        change_set = change_set_service.create("workspace-1", "add binding-2")
        change_set = change_set_service.add_operation(
            change_set.change_set_id, _operation("op-1", "add", "binding", "binding-2")
        )

        result = rebase_service.rebase(change_set.change_set_id)

        assert isinstance(result, RebaseResult)
        assert result.successful is True
        assert result.conflicts == ()
        assert result.rebased_operations == change_set.operations
        assert rebase_service.requires_review(change_set.change_set_id) is True

        version_service.publish("workspace-1", "v2")

        second_result = rebase_service.rebase(change_set.change_set_id)
        assert second_result.successful is True

        history = rebase_service.rebase_history("workspace-1")
        assert len(history) == 2
        assert history[0].source_revision is None
        assert history[0].target_revision == "v1"
        assert history[0].status == RebaseStatus.SUCCEEDED
        assert history[1].source_revision == "v1"
        assert history[1].target_revision == "v2"
        assert history[1].status == RebaseStatus.SUCCEEDED

    def test_preview_rebase(self):
        workspace_service, change_set_service, conflict_service, version_service, rebase_service = _build()

        version_service.publish("workspace-1", "v1")

        change_set = change_set_service.create("workspace-1", "add binding-2")
        change_set = change_set_service.add_operation(
            change_set.change_set_id, _operation("op-1", "add", "binding", "binding-2")
        )

        preview = rebase_service.preview_rebase(change_set.change_set_id)

        assert preview.successful is True
        assert preview.rebased_operations == change_set.operations

        # preview must not mutate tracked revision, review flag, or history
        assert rebase_service.requires_review(change_set.change_set_id) is False
        assert rebase_service.rebase_history("workspace-1") == ()
        assert rebase_service.can_rebase(change_set.change_set_id) is True

    def test_rebase_with_conflicts(self):
        workspace_service, change_set_service, conflict_service, version_service, rebase_service = _build()

        version_service.publish("workspace-1", "v1")

        change_set = change_set_service.create("workspace-1", "stale add")
        change_set_service.add_operation(change_set.change_set_id, _operation("op-1", "add", "binding", "binding-1"))

        result = rebase_service.rebase(change_set.change_set_id)

        assert result.successful is False
        assert result.rebased_operations == ()
        assert len(result.conflicts) >= 1
        assert all(conflict.conflict_type == "stale_state" for conflict in result.conflicts)

        assert rebase_service.requires_review(change_set.change_set_id) is False

        history = rebase_service.rebase_history("workspace-1")
        assert len(history) == 1
        assert history[0].status == RebaseStatus.FAILED

    def test_no_op_rebase(self):
        workspace_service, change_set_service, conflict_service, version_service, rebase_service = _build()

        version_service.publish("workspace-1", "v1")

        change_set = change_set_service.create("workspace-1", "add binding-2")
        change_set_service.add_operation(change_set.change_set_id, _operation("op-1", "add", "binding", "binding-2"))

        rebase_service.rebase(change_set.change_set_id)

        # no new revision has been published since; nothing left to rebase
        assert rebase_service.can_rebase(change_set.change_set_id) is False

        with pytest.raises(RebaseError):
            rebase_service.rebase(change_set.change_set_id)

        with pytest.raises(RebaseError):
            rebase_service.preview_rebase(change_set.change_set_id)

    def test_re_review_required_after_changes(self):
        workspace_service, change_set_service, conflict_service, version_service, rebase_service = _build()

        version_service.publish("workspace-1", "v1")

        change_set = change_set_service.create("workspace-1", "add binding-2")
        change_set_service.add_operation(change_set.change_set_id, _operation("op-1", "add", "binding", "binding-2"))

        assert rebase_service.requires_review(change_set.change_set_id) is False

        rebase_service.rebase(change_set.change_set_id)

        assert rebase_service.requires_review(change_set.change_set_id) is True

    def test_rebase_history_retrieval(self):
        workspace_service, change_set_service, conflict_service, version_service, rebase_service = _build()

        version_service.publish("workspace-1", "v1")

        first = change_set_service.create("workspace-1", "first")
        change_set_service.add_operation(first.change_set_id, _operation("op-1", "add", "binding", "binding-2"))
        rebase_service.rebase(first.change_set_id)

        second = change_set_service.create("workspace-1", "second")
        change_set_service.add_operation(second.change_set_id, _operation("op-1", "add", "binding", "binding-3"))
        rebase_service.rebase(second.change_set_id)

        history = rebase_service.rebase_history("workspace-1")

        assert len(history) == 2
        assert history[0].change_set_id == first.change_set_id
        assert history[1].change_set_id == second.change_set_id
        assert all(isinstance(record, ChangeSetRebase) for record in history)

        assert rebase_service.rebase_history("workspace-2") == ()

        with pytest.raises(RebaseError):
            rebase_service.rebase_history("   ")

    def test_reject_unknown_revision(self):
        workspace_service, change_set_service, conflict_service, version_service, rebase_service = _build()

        change_set = change_set_service.create("workspace-1", "no revisions yet")
        change_set_service.add_operation(change_set.change_set_id, _operation("op-1", "add", "binding", "binding-2"))

        with pytest.raises(RebaseError):
            rebase_service.rebase(change_set.change_set_id)

        with pytest.raises(RebaseError):
            rebase_service.can_rebase(change_set.change_set_id)

        with pytest.raises(RebaseError):
            rebase_service.preview_rebase(change_set.change_set_id)

    def test_reject_blank_ids(self):
        workspace_service, change_set_service, conflict_service, version_service, rebase_service = _build()

        with pytest.raises(RebaseError):
            rebase_service.rebase("   ")

        with pytest.raises(RebaseError):
            rebase_service.can_rebase("   ")

        with pytest.raises(RebaseError):
            rebase_service.preview_rebase("   ")

        with pytest.raises(RebaseError):
            rebase_service.rebase_history("   ")

        with pytest.raises(RebaseError):
            rebase_service.requires_review("   ")

    def test_reject_unknown_change_set(self):
        workspace_service, change_set_service, conflict_service, version_service, rebase_service = _build()

        with pytest.raises(RebaseError):
            rebase_service.rebase("unknown-change-set")

        with pytest.raises(RebaseError):
            rebase_service.can_rebase("unknown-change-set")

    def test_reject_non_open_change_set(self):
        workspace_service, change_set_service, conflict_service, version_service, rebase_service = _build()

        version_service.publish("workspace-1", "v1")

        change_set = change_set_service.create("workspace-1", "will discard")
        change_set_service.add_operation(change_set.change_set_id, _operation("op-1", "add", "binding", "binding-2"))
        change_set_service.discard(change_set.change_set_id)

        with pytest.raises(RebaseError):
            rebase_service.rebase(change_set.change_set_id)

        assert rebase_service.can_rebase(change_set.change_set_id) is False

    def test_reject_invalid_constructor_arguments(self):
        workspace_service, change_set_service, conflict_service, version_service, rebase_service = _build()

        with pytest.raises(RebaseError):
            RebaseService(None, version_service, conflict_service)

        with pytest.raises(RebaseError):
            RebaseService(change_set_service, None, conflict_service)

        with pytest.raises(RebaseError):
            RebaseService(change_set_service, version_service, None)

    def test_operation_order_preserved(self):
        workspace_service, change_set_service, conflict_service, version_service, rebase_service = _build()

        version_service.publish("workspace-1", "v1")

        change_set = change_set_service.create("workspace-1", "ordered")
        change_set_service.add_operation(change_set.change_set_id, _operation("op-1", "add", "binding", "binding-2"))
        change_set_service.add_operation(change_set.change_set_id, _operation("op-2", "add", "binding", "binding-3"))

        result = rebase_service.rebase(change_set.change_set_id)

        assert [operation.operation_id for operation in result.rebased_operations] == ["op-1", "op-2"]
