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
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeConflict as ChangeConflict,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeOperation as ChangeOperation,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetService as ChangeSetService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceConflictError as ConflictError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceConflictResolutionStatus as ResolutionStatus,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceConflictService as ConflictService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceService as WorkspaceService,
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

    change_set_service = ChangeSetService(workspace_service)
    conflict_service = ConflictService(change_set_service, workspace_service)

    return workspace_service, change_set_service, conflict_service


class TestBindingWorkspaceConflictService:
    def test_detect_conflicts(self):
        workspace_service, change_set_service, conflict_service = _build()

        change_set = change_set_service.create("workspace-1", "stale add")
        change_set_service.add_operation(
            change_set.change_set_id, _operation("op-1", "add", "binding", "binding-1")
        )

        conflicts = conflict_service.detect(change_set.change_set_id)

        assert len(conflicts) == 1
        assert isinstance(conflicts[0], ChangeConflict)
        assert conflicts[0].resource_id == "binding-1"
        assert conflicts[0].conflict_type == "stale_state"
        assert conflicts[0].resolution_status == ResolutionStatus.UNRESOLVED

        with pytest.raises(ConflictError):
            conflict_service.detect("unknown-change-set")

    def test_detect_no_conflicts_for_clean_change_set(self):
        workspace_service, change_set_service, conflict_service = _build()

        change_set = change_set_service.create("workspace-1", "clean add")
        change_set_service.add_operation(
            change_set.change_set_id, _operation("op-1", "add", "binding", "binding-2")
        )

        conflicts = conflict_service.detect(change_set.change_set_id)

        assert conflicts == ()

    def test_detect_concurrent_edit_conflicts(self):
        workspace_service, change_set_service, conflict_service = _build()

        first = change_set_service.create("workspace-1", "first")
        change_set_service.add_operation(first.change_set_id, _operation("op-1", "add", "binding", "binding-2"))

        second = change_set_service.create("workspace-1", "second")
        change_set_service.add_operation(second.change_set_id, _operation("op-1", "add", "binding", "binding-2"))

        conflicts = conflict_service.detect(first.change_set_id)

        assert len(conflicts) == 1
        assert conflicts[0].conflict_type == "concurrent_edit"
        assert conflicts[0].resource_id == "binding-2"

    def test_resolve_manually(self):
        workspace_service, change_set_service, conflict_service = _build()

        change_set = change_set_service.create("workspace-1", "stale add")
        change_set_service.add_operation(
            change_set.change_set_id, _operation("op-1", "add", "binding", "binding-1")
        )

        conflicts = conflict_service.detect(change_set.change_set_id)
        conflict_id = conflicts[0].conflict_id

        resolution = conflict_service.resolve(conflict_id, "manual")

        assert resolution.conflict_id == conflict_id
        assert resolution.strategy == "manual"
        assert resolution.resolved_at is not None
        assert conflict_service.find(conflict_id).resolution_status == ResolutionStatus.RESOLVED

    def test_auto_resolve_supported_conflicts(self):
        workspace_service, change_set_service, conflict_service = _build()

        change_set = change_set_service.create("workspace-1", "stale add")
        change_set_service.add_operation(
            change_set.change_set_id, _operation("op-1", "add", "binding", "binding-1")
        )

        conflicts = conflict_service.detect(change_set.change_set_id)
        conflict_id = conflicts[0].conflict_id

        resolution = conflict_service.resolve(conflict_id, "auto")

        assert resolution.strategy == "auto"
        assert conflict_service.find(conflict_id).resolution_status == ResolutionStatus.RESOLVED

    def test_auto_resolve_unsupported_conflict_rejected(self):
        workspace_service, change_set_service, conflict_service = _build()

        first = change_set_service.create("workspace-1", "first")
        change_set_service.add_operation(first.change_set_id, _operation("op-1", "add", "binding", "binding-2"))

        second = change_set_service.create("workspace-1", "second")
        change_set_service.add_operation(second.change_set_id, _operation("op-1", "add", "binding", "binding-2"))

        conflicts = conflict_service.detect(first.change_set_id)
        assert conflicts[0].conflict_type == "concurrent_edit"

        with pytest.raises(ConflictError):
            conflict_service.resolve(conflicts[0].conflict_id, "auto")

        resolution = conflict_service.resolve(conflicts[0].conflict_id, "manual")
        assert resolution.strategy == "manual"

    def test_unresolved_conflicts_block_apply(self):
        workspace_service, change_set_service, conflict_service = _build()

        change_set = change_set_service.create("workspace-1", "stale add")
        change_set_service.add_operation(
            change_set.change_set_id, _operation("op-1", "add", "binding", "binding-1")
        )

        assert conflict_service.can_apply(change_set.change_set_id) is True

        conflicts = conflict_service.detect(change_set.change_set_id)
        assert conflict_service.can_apply(change_set.change_set_id) is False

        conflict_service.resolve(conflicts[0].conflict_id, "manual")
        assert conflict_service.can_apply(change_set.change_set_id) is True

        change_set_service.remove_operation(change_set.change_set_id, "op-1")
        change_set_service.add_operation(
            change_set.change_set_id, _operation("op-2", "add", "binding", "binding-2")
        )
        change_set_service.apply(change_set.change_set_id)

        assert conflict_service.can_apply(change_set.change_set_id) is False

    def test_invalid_strategy_rejection(self):
        workspace_service, change_set_service, conflict_service = _build()

        change_set = change_set_service.create("workspace-1", "stale add")
        change_set_service.add_operation(
            change_set.change_set_id, _operation("op-1", "add", "binding", "binding-1")
        )

        conflicts = conflict_service.detect(change_set.change_set_id)

        with pytest.raises(ConflictError):
            conflict_service.resolve(conflicts[0].conflict_id, "magic")

        with pytest.raises(ConflictError):
            conflict_service.resolve(conflicts[0].conflict_id, "   ")

    def test_resolving_already_resolved_conflict_rejected(self):
        workspace_service, change_set_service, conflict_service = _build()

        change_set = change_set_service.create("workspace-1", "stale add")
        change_set_service.add_operation(
            change_set.change_set_id, _operation("op-1", "add", "binding", "binding-1")
        )

        conflicts = conflict_service.detect(change_set.change_set_id)
        conflict_service.resolve(conflicts[0].conflict_id, "manual")

        with pytest.raises(ConflictError):
            conflict_service.resolve(conflicts[0].conflict_id, "manual")

    def test_conflict_history_retained(self):
        workspace_service, change_set_service, conflict_service = _build()

        change_set = change_set_service.create("workspace-1", "stale add")
        change_set_service.add_operation(
            change_set.change_set_id, _operation("op-1", "add", "binding", "binding-1")
        )

        conflicts = conflict_service.detect(change_set.change_set_id)
        conflict_id = conflicts[0].conflict_id

        conflict_service.resolve(conflict_id, "manual")

        # re-detecting does not duplicate the now-resolved conflict
        conflicts_again = conflict_service.detect(change_set.change_set_id)

        assert len(conflicts_again) == 1
        assert conflicts_again[0].conflict_id == conflict_id
        assert conflicts_again[0].resolution_status == ResolutionStatus.RESOLVED

        assert conflict_service.remaining(change_set.change_set_id) == ()
        assert len(conflict_service.history(change_set.change_set_id)) == 1

    def test_reject_blank_ids(self):
        workspace_service, change_set_service, conflict_service = _build()

        with pytest.raises(ConflictError):
            conflict_service.detect("   ")

        with pytest.raises(ConflictError):
            conflict_service.resolve("   ", "manual")

        with pytest.raises(ConflictError):
            conflict_service.remaining("   ")

        with pytest.raises(ConflictError):
            conflict_service.can_apply("   ")

        with pytest.raises(ConflictError):
            conflict_service.find("   ")

    def test_reject_unknown_conflict(self):
        workspace_service, change_set_service, conflict_service = _build()

        with pytest.raises(ConflictError):
            conflict_service.resolve("unknown-conflict", "manual")

        assert conflict_service.find("unknown-conflict") is None

    def test_reject_invalid_constructor_arguments(self):
        workspace_service, change_set_service, conflict_service = _build()

        with pytest.raises(ConflictError):
            ConflictService(None, workspace_service)

        with pytest.raises(ConflictError):
            ConflictService(change_set_service, None)

    def test_reject_invalid_conflict_model_arguments(self):
        with pytest.raises(ConflictError):
            ChangeConflict(
                conflict_id="   ",
                change_set_id="change-set-1",
                resource_id="binding-1",
                conflict_type="stale_state",
                resolution_status=ResolutionStatus.UNRESOLVED,
            )

        with pytest.raises(ConflictError):
            ChangeConflict(
                conflict_id="conflict-1",
                change_set_id="change-set-1",
                resource_id="binding-1",
                conflict_type="not_a_real_type",
                resolution_status=ResolutionStatus.UNRESOLVED,
            )
