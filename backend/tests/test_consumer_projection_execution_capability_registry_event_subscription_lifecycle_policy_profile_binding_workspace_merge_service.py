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
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetApprovalPolicy as ApprovalPolicy,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewService as ReviewService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetService as ChangeSetService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceConflictService as ConflictService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceMergeError as MergeError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceMergeResult as MergeResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceMergeService as MergeService,
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

    for binding_id in ("binding-1", "binding-2", "binding-3", "binding-4", "binding-5"):
        binding_service.register(_binding(binding_id))

    workspace_service = WorkspaceService(binding_service, template_service, preset_service, group_service)
    workspace_service.create(_workspace("workspace-1", binding_ids=("binding-1",)))
    workspace_service.create(_workspace("workspace-2", binding_ids=()))

    change_set_service = ChangeSetService(workspace_service)
    policy = ApprovalPolicy(minimum_approvals=1, require_unanimous=False)
    review_service = ReviewService(change_set_service, policy)
    conflict_service = ConflictService(change_set_service, workspace_service)
    merge_service = MergeService(change_set_service, review_service, conflict_service)

    return workspace_service, change_set_service, review_service, conflict_service, merge_service


def _approved_change_set(change_set_service, review_service, workspace_id, name, operations, reviewer="reviewer-a"):
    change_set = change_set_service.create(workspace_id, name)

    for operation in operations:
        change_set_service.add_operation(change_set.change_set_id, operation)

    review = review_service.submit(change_set.change_set_id, reviewer)
    review_service.approve(review.review_id)

    return change_set


class TestBindingWorkspaceMergeService:
    def test_successful_merge(self):
        workspace_service, change_set_service, review_service, conflict_service, merge_service = _build()

        first = _approved_change_set(
            change_set_service,
            review_service,
            "workspace-1",
            "first",
            [_operation("op-1", "add", "binding", "binding-2")],
        )
        second = _approved_change_set(
            change_set_service,
            review_service,
            "workspace-1",
            "second",
            [_operation("op-1", "add", "binding", "binding-3")],
        )

        result = merge_service.merge([first.change_set_id, second.change_set_id])

        assert isinstance(result, MergeResult)
        assert result.successful is True
        assert result.conflicts_detected == ()
        assert len(result.merged_operations) == 2
        assert [operation.resource_id for operation in result.merged_operations] == ["binding-2", "binding-3"]

        # operation IDs are namespaced per source, so identical source IDs never collide
        assert result.merged_operations[0].operation_id == f"{first.change_set_id}:op-1"
        assert result.merged_operations[1].operation_id == f"{second.change_set_id}:op-1"

        history = merge_service.merge_history("workspace-1")
        assert len(history) == 1
        assert history[0].source_change_set_ids == (first.change_set_id, second.change_set_id)

        merged_change_set = change_set_service.find(history[0].merged_change_set_id)
        assert merged_change_set is not None
        assert merged_change_set.operations == result.merged_operations

    def test_merge_preview(self):
        workspace_service, change_set_service, review_service, conflict_service, merge_service = _build()

        first = _approved_change_set(
            change_set_service,
            review_service,
            "workspace-1",
            "first",
            [_operation("op-1", "add", "binding", "binding-2")],
        )
        second = _approved_change_set(
            change_set_service,
            review_service,
            "workspace-1",
            "second",
            [_operation("op-1", "add", "binding", "binding-3")],
        )

        before_count = len(change_set_service.list())

        preview = merge_service.preview_merge([first.change_set_id, second.change_set_id])

        assert preview.successful is True
        assert len(preview.merged_operations) == 2

        assert len(change_set_service.list()) == before_count
        assert merge_service.merge_history("workspace-1") == ()

    def test_merge_conflict_detection(self):
        workspace_service, change_set_service, review_service, conflict_service, merge_service = _build()

        first = _approved_change_set(
            change_set_service,
            review_service,
            "workspace-1",
            "first",
            [_operation("op-1", "add", "binding", "binding-2")],
            reviewer="reviewer-a",
        )
        second = _approved_change_set(
            change_set_service,
            review_service,
            "workspace-1",
            "second",
            [_operation("op-1", "add", "binding", "binding-2")],
            reviewer="reviewer-b",
        )

        assert merge_service.can_merge([first.change_set_id, second.change_set_id]) is False

        result = merge_service.merge([first.change_set_id, second.change_set_id])

        assert result.successful is False
        assert result.merged_operations == ()
        assert len(result.conflicts_detected) >= 1
        assert all(conflict.conflict_type == "concurrent_edit" for conflict in result.conflicts_detected)

        assert merge_service.merge_history("workspace-1") == ()

    def test_cross_workspace_rejection(self):
        workspace_service, change_set_service, review_service, conflict_service, merge_service = _build()

        first = _approved_change_set(
            change_set_service,
            review_service,
            "workspace-1",
            "first",
            [_operation("op-1", "add", "binding", "binding-2")],
        )
        second = _approved_change_set(
            change_set_service,
            review_service,
            "workspace-2",
            "second",
            [],
        )

        with pytest.raises(MergeError):
            merge_service.merge([first.change_set_id, second.change_set_id])

        with pytest.raises(MergeError):
            merge_service.preview_merge([first.change_set_id, second.change_set_id])

        assert merge_service.can_merge([first.change_set_id, second.change_set_id]) is False

    def test_duplicate_change_set_rejection(self):
        workspace_service, change_set_service, review_service, conflict_service, merge_service = _build()

        first = _approved_change_set(
            change_set_service,
            review_service,
            "workspace-1",
            "first",
            [_operation("op-1", "add", "binding", "binding-2")],
        )

        with pytest.raises(MergeError):
            merge_service.merge([first.change_set_id, first.change_set_id])

        with pytest.raises(MergeError):
            merge_service.preview_merge([first.change_set_id, first.change_set_id])

    def test_merge_history_retrieval(self):
        workspace_service, change_set_service, review_service, conflict_service, merge_service = _build()

        first = _approved_change_set(
            change_set_service,
            review_service,
            "workspace-1",
            "first",
            [_operation("op-1", "add", "binding", "binding-2")],
        )
        merge_service.merge([first.change_set_id])

        second = _approved_change_set(
            change_set_service,
            review_service,
            "workspace-1",
            "second",
            [_operation("op-1", "add", "binding", "binding-3")],
        )
        merge_service.merge([second.change_set_id])

        history = merge_service.merge_history("workspace-1")

        assert len(history) == 2
        assert history[0].source_change_set_ids == (first.change_set_id,)
        assert history[1].source_change_set_ids == (second.change_set_id,)
        assert history[0].merged_at <= history[1].merged_at

        assert merge_service.merge_history("workspace-2") == ()

        with pytest.raises(MergeError):
            merge_service.merge_history("   ")

    def test_unapproved_change_set_rejection(self):
        workspace_service, change_set_service, review_service, conflict_service, merge_service = _build()

        change_set = change_set_service.create("workspace-1", "unapproved")
        change_set_service.add_operation(
            change_set.change_set_id, _operation("op-1", "add", "binding", "binding-2")
        )

        with pytest.raises(MergeError):
            merge_service.merge([change_set.change_set_id])

        assert merge_service.can_merge([change_set.change_set_id]) is False

    def test_reject_blank_and_empty_ids(self):
        workspace_service, change_set_service, review_service, conflict_service, merge_service = _build()

        with pytest.raises(MergeError):
            merge_service.merge(None)

        with pytest.raises(MergeError):
            merge_service.merge([])

        with pytest.raises(MergeError):
            merge_service.merge(["   "])

        with pytest.raises(MergeError):
            merge_service.can_merge(None)

    def test_reject_unknown_change_set(self):
        workspace_service, change_set_service, review_service, conflict_service, merge_service = _build()

        with pytest.raises(MergeError):
            merge_service.merge(["unknown-change-set"])

        with pytest.raises(MergeError):
            merge_service.can_merge(["unknown-change-set"])

    def test_reject_invalid_constructor_arguments(self):
        workspace_service, change_set_service, review_service, conflict_service, merge_service = _build()

        with pytest.raises(MergeError):
            MergeService(None, review_service, conflict_service)

        with pytest.raises(MergeError):
            MergeService(change_set_service, None, conflict_service)

        with pytest.raises(MergeError):
            MergeService(change_set_service, review_service, None)

    def test_operation_order_preserved_across_sources(self):
        workspace_service, change_set_service, review_service, conflict_service, merge_service = _build()

        first = _approved_change_set(
            change_set_service,
            review_service,
            "workspace-1",
            "first",
            [
                _operation("op-1", "add", "binding", "binding-2"),
                _operation("op-2", "add", "binding", "binding-3"),
            ],
        )
        second = _approved_change_set(
            change_set_service,
            review_service,
            "workspace-1",
            "second",
            [
                _operation("op-1", "add", "binding", "binding-4"),
                _operation("op-2", "add", "binding", "binding-5"),
            ],
        )

        result = merge_service.merge([first.change_set_id, second.change_set_id])

        assert [operation.resource_id for operation in result.merged_operations] == [
            "binding-2",
            "binding-3",
            "binding-4",
            "binding-5",
        ]
