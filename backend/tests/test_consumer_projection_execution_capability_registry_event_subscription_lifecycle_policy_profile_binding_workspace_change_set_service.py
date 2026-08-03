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
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSet as ChangeSet,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetError as ChangeSetError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetPreview as ChangeSetPreview,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetService as ChangeSetService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetStatus as ChangeSetStatus,
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


def _operation(operation_id, operation_type, resource_type, resource_id, payload=None):
    return ChangeOperation(
        operation_id=operation_id,
        operation_type=operation_type,
        resource_type=resource_type,
        resource_id=resource_id,
        payload=payload,
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

    return workspace_service, change_set_service


class TestBindingWorkspaceChangeSetService:
    def test_create_apply_discard_change_set(self):
        workspace_service, service = _build()

        change_set = service.create("workspace-1", "add binding-2")

        assert change_set.status == ChangeSetStatus.OPEN
        assert change_set.operations == ()

        service.add_operation(change_set.change_set_id, _operation("op-1", "add", "binding", "binding-2"))

        applied = service.apply(change_set.change_set_id)

        assert applied.status == ChangeSetStatus.APPLIED
        assert workspace_service.find("workspace-1").binding_ids == ("binding-1", "binding-2")

        discard_set = service.create("workspace-1", "discard me")
        service.add_operation(discard_set.change_set_id, _operation("op-1", "add", "binding", "binding-3"))

        discarded = service.discard(discard_set.change_set_id)

        assert discarded.status == ChangeSetStatus.DISCARDED
        assert workspace_service.find("workspace-1").binding_ids == ("binding-1", "binding-2")

        with pytest.raises(ChangeSetError):
            service.create("workspace-unknown", "name")

    def test_preview_changes(self):
        workspace_service, service = _build()

        change_set = service.create("workspace-1", "preview test")

        service.add_operation(change_set.change_set_id, _operation("op-1", "add", "binding", "binding-2"))
        service.add_operation(change_set.change_set_id, _operation("op-2", "remove", "binding", "binding-1"))

        preview = service.preview(change_set.change_set_id)

        assert isinstance(preview, ChangeSetPreview)
        assert preview.change_set_id == change_set.change_set_id
        assert preview.workspace_id == "workspace-1"
        assert preview.binding_ids == ("binding-2",)
        assert preview.template_ids == ()
        assert preview.preset_ids == ()
        assert preview.group_ids == ()

    def test_preview_leaves_workspace_unchanged(self):
        workspace_service, service = _build()

        change_set = service.create("workspace-1", "preview test")
        service.add_operation(change_set.change_set_id, _operation("op-1", "add", "binding", "binding-2"))

        service.preview(change_set.change_set_id)
        service.preview(change_set.change_set_id)

        assert workspace_service.find("workspace-1").binding_ids == ("binding-1",)
        assert service.find(change_set.change_set_id).status == ChangeSetStatus.OPEN
        assert service.find(change_set.change_set_id).operations[0].operation_id == "op-1"

    def test_operation_ordering(self):
        workspace_service, service = _build()

        change_set = service.create("workspace-1", "order test")

        service.add_operation(change_set.change_set_id, _operation("op-1", "add", "binding", "binding-2"))
        service.add_operation(change_set.change_set_id, _operation("op-2", "add", "binding", "binding-3"))
        service.add_operation(change_set.change_set_id, _operation("op-3", "remove", "binding", "binding-2"))

        staged = service.find(change_set.change_set_id)

        assert [operation.operation_id for operation in staged.operations] == ["op-1", "op-2", "op-3"]

        service.apply(change_set.change_set_id)

        assert workspace_service.find("workspace-1").binding_ids == ("binding-1", "binding-3")

    def test_atomic_apply(self):
        workspace_service, service = _build()

        change_set = service.create("workspace-1", "atomic test")

        service.add_operation(change_set.change_set_id, _operation("op-1", "add", "binding", "binding-2"))
        service.add_operation(change_set.change_set_id, _operation("op-2", "remove", "binding", "binding-unknown"))

        with pytest.raises(ChangeSetError):
            service.apply(change_set.change_set_id)

        assert workspace_service.find("workspace-1").binding_ids == ("binding-1",)
        assert service.find(change_set.change_set_id).status == ChangeSetStatus.OPEN

    def test_duplicate_operation_rejection(self):
        workspace_service, service = _build()

        change_set = service.create("workspace-1", "dup test")
        service.add_operation(change_set.change_set_id, _operation("op-1", "add", "binding", "binding-2"))

        with pytest.raises(ChangeSetError):
            service.add_operation(change_set.change_set_id, _operation("op-1", "add", "binding", "binding-3"))

        with pytest.raises(ChangeSetError):
            ChangeSet(
                change_set_id="change-set-1",
                workspace_id="workspace-1",
                name="dup",
                description=None,
                operations=(
                    _operation("op-1", "add", "binding", "binding-2"),
                    _operation("op-1", "remove", "binding", "binding-2"),
                ),
                status=ChangeSetStatus.OPEN,
                created_at=datetime.now(timezone.utc),
            )

    def test_invalid_state_transition(self):
        workspace_service, service = _build()

        change_set = service.create("workspace-1", "state test")
        service.add_operation(change_set.change_set_id, _operation("op-1", "add", "binding", "binding-2"))
        service.apply(change_set.change_set_id)

        with pytest.raises(ChangeSetError):
            service.add_operation(change_set.change_set_id, _operation("op-2", "add", "binding", "binding-3"))

        with pytest.raises(ChangeSetError):
            service.remove_operation(change_set.change_set_id, "op-1")

        with pytest.raises(ChangeSetError):
            service.apply(change_set.change_set_id)

        with pytest.raises(ChangeSetError):
            service.discard(change_set.change_set_id)

        discard_set = service.create("workspace-1", "discard test")
        service.discard(discard_set.change_set_id)

        with pytest.raises(ChangeSetError):
            service.discard(discard_set.change_set_id)

    def test_reject_blank_ids_and_empty_change_sets(self):
        workspace_service, service = _build()

        with pytest.raises(ChangeSetError):
            service.create("   ", "name")

        with pytest.raises(ChangeSetError):
            service.create("workspace-1", "   ")

        change_set = service.create("workspace-1", "empty test")

        with pytest.raises(ChangeSetError):
            service.apply(change_set.change_set_id)

        with pytest.raises(ChangeSetError):
            service.find("   ")

    def test_reject_unknown_change_set_and_operation(self):
        workspace_service, service = _build()

        with pytest.raises(ChangeSetError):
            service.add_operation("missing-change-set", _operation("op-1", "add", "binding", "binding-2"))

        change_set = service.create("workspace-1", "x")

        with pytest.raises(ChangeSetError):
            service.remove_operation(change_set.change_set_id, "missing-operation")

    def test_reject_invalid_operations(self):
        with pytest.raises(ChangeSetError):
            _operation("   ", "add", "binding", "binding-1")

        with pytest.raises(ChangeSetError):
            _operation("op-1", "modify", "binding", "binding-1")

        with pytest.raises(ChangeSetError):
            _operation("op-1", "add", "widget", "binding-1")

        with pytest.raises(ChangeSetError):
            _operation("op-1", "add", "binding", "   ")

        with pytest.raises(ChangeSetError):
            _operation("op-1", "add", "binding", "binding-1", payload="not-a-mapping")

    def test_reject_none_workspace_service(self):
        with pytest.raises(ChangeSetError):
            ChangeSetService(None)
