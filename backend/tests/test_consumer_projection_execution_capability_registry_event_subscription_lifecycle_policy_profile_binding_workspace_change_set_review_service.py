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
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewError as ReviewError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewService as ReviewService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewStatus as ReviewStatus,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetService as ChangeSetService,
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


def _build(minimum_approvals=1, require_unanimous=False):
    binding_service = BindingRegistryService()
    template_service = TemplateRegistryService()
    preset_service = PresetRegistryService()
    group_service = GroupRegistryService()

    for binding_id in ("binding-1", "binding-2"):
        binding_service.register(_binding(binding_id))

    workspace_service = WorkspaceService(binding_service, template_service, preset_service, group_service)
    workspace_service.create(_workspace("workspace-1", binding_ids=("binding-1",)))

    change_set_service = ChangeSetService(workspace_service)
    change_set = change_set_service.create("workspace-1", "add binding-2")
    change_set_service.add_operation(
        change_set.change_set_id,
        ChangeOperation(
            operation_id="op-1",
            operation_type="add",
            resource_type="binding",
            resource_id="binding-2",
        ),
    )

    policy = ApprovalPolicy(minimum_approvals=minimum_approvals, require_unanimous=require_unanimous)
    review_service = ReviewService(change_set_service, policy)

    return change_set_service, review_service, change_set.change_set_id


class TestBindingWorkspaceChangeSetReviewService:
    def test_submit_for_review(self):
        _, review_service, change_set_id = _build()

        review = review_service.submit(change_set_id, "reviewer-a")

        assert review.status == ReviewStatus.PENDING
        assert review.change_set_id == change_set_id
        assert review.reviewer == "reviewer-a"
        assert review.reviewed_at is None

        assert review_service.status(change_set_id) == ReviewStatus.PENDING

        with pytest.raises(ReviewError):
            review_service.submit("unknown-change-set", "reviewer-b")

    def test_approve_and_reject_review(self):
        _, review_service, change_set_id = _build()

        approved_review = review_service.submit(change_set_id, "reviewer-a")
        approved = review_service.approve(approved_review.review_id, comments="looks good")

        assert approved.status == ReviewStatus.APPROVED
        assert approved.comments == "looks good"
        assert approved.reviewed_at is not None

        rejected_review = review_service.submit(change_set_id, "reviewer-b")
        rejected = review_service.reject(rejected_review.review_id, comments="needs changes")

        assert rejected.status == ReviewStatus.REJECTED
        assert rejected.comments == "needs changes"
        assert rejected.reviewed_at is not None

    def test_approval_policy_enforcement(self):
        _, review_service, change_set_id = _build(minimum_approvals=2, require_unanimous=False)

        review_a = review_service.submit(change_set_id, "reviewer-a")
        assert review_service.status(change_set_id) == ReviewStatus.PENDING

        review_service.approve(review_a.review_id)
        assert review_service.status(change_set_id) == ReviewStatus.PENDING

        review_b = review_service.submit(change_set_id, "reviewer-b")
        review_service.approve(review_b.review_id)
        assert review_service.status(change_set_id) == ReviewStatus.APPROVED

    def test_unanimous_approval_policy(self):
        _, review_service, change_set_id = _build(minimum_approvals=2, require_unanimous=True)

        review_a = review_service.submit(change_set_id, "reviewer-a")
        review_b = review_service.submit(change_set_id, "reviewer-b")

        review_service.approve(review_a.review_id)
        assert review_service.status(change_set_id) == ReviewStatus.PENDING

        review_service.reject(review_b.review_id)
        assert review_service.status(change_set_id) == ReviewStatus.REJECTED

        resubmitted = review_service.submit(change_set_id, "reviewer-b")
        review_service.approve(resubmitted.review_id)
        assert review_service.status(change_set_id) == ReviewStatus.APPROVED

    def test_can_apply_true_and_false(self):
        change_set_service, review_service, change_set_id = _build(minimum_approvals=1)

        assert review_service.can_apply(change_set_id) is False

        review = review_service.submit(change_set_id, "reviewer-a")
        assert review_service.can_apply(change_set_id) is False

        review_service.approve(review.review_id)
        assert review_service.can_apply(change_set_id) is True

        change_set_service.apply(change_set_id)
        assert review_service.can_apply(change_set_id) is False

    def test_rejected_change_set_cannot_apply_until_resubmitted(self):
        _, review_service, change_set_id = _build(minimum_approvals=1)

        review = review_service.submit(change_set_id, "reviewer-a")
        review_service.reject(review.review_id)

        assert review_service.can_apply(change_set_id) is False

        resubmitted = review_service.submit(change_set_id, "reviewer-a")
        assert review_service.can_apply(change_set_id) is False

        review_service.approve(resubmitted.review_id)
        assert review_service.can_apply(change_set_id) is True

    def test_duplicate_reviewer_rejection(self):
        _, review_service, change_set_id = _build()

        review_service.submit(change_set_id, "reviewer-a")

        with pytest.raises(ReviewError):
            review_service.submit(change_set_id, "reviewer-a")

    def test_duplicate_reviewer_allowed_after_rejection(self):
        _, review_service, change_set_id = _build()

        first = review_service.submit(change_set_id, "reviewer-a")
        review_service.reject(first.review_id)

        second = review_service.submit(change_set_id, "reviewer-a")

        assert second.review_id != first.review_id
        assert second.status == ReviewStatus.PENDING

    def test_invalid_transition_rejection(self):
        _, review_service, change_set_id = _build()

        review = review_service.submit(change_set_id, "reviewer-a")
        review_service.approve(review.review_id)

        with pytest.raises(ReviewError):
            review_service.approve(review.review_id)

        with pytest.raises(ReviewError):
            review_service.reject(review.review_id)

    def test_review_after_application_rejected(self):
        change_set_service, review_service, change_set_id = _build()

        review = review_service.submit(change_set_id, "reviewer-a")
        review_service.approve(review.review_id)

        change_set_service.apply(change_set_id)

        with pytest.raises(ReviewError):
            review_service.submit(change_set_id, "reviewer-b")

        with pytest.raises(ReviewError):
            review_service.approve(review.review_id)

    def test_review_history_retained(self):
        _, review_service, change_set_id = _build()

        first = review_service.submit(change_set_id, "reviewer-a")
        review_service.reject(first.review_id)

        second = review_service.submit(change_set_id, "reviewer-a")
        review_service.approve(second.review_id)

        history = review_service.history(change_set_id)

        assert [entry.review_id for entry in history] == [first.review_id, second.review_id]
        assert review_service.find(first.review_id).status == ReviewStatus.REJECTED
        assert review_service.find(second.review_id).status == ReviewStatus.APPROVED

    def test_reject_blank_ids(self):
        _, review_service, change_set_id = _build()

        with pytest.raises(ReviewError):
            review_service.submit("   ", "reviewer-a")

        with pytest.raises(ReviewError):
            review_service.submit(change_set_id, "   ")

        with pytest.raises(ReviewError):
            review_service.approve("   ")

        with pytest.raises(ReviewError):
            review_service.status("   ")

        with pytest.raises(ReviewError):
            review_service.can_apply("   ")

    def test_reject_unknown_review(self):
        _, review_service, change_set_id = _build()

        with pytest.raises(ReviewError):
            review_service.approve("unknown-review")

        with pytest.raises(ReviewError):
            review_service.reject("unknown-review")

    def test_reject_invalid_constructor_arguments(self):
        _, _, change_set_id = _build()

        change_set_service = ChangeSetService(
            WorkspaceService(
                BindingRegistryService(),
                TemplateRegistryService(),
                PresetRegistryService(),
                GroupRegistryService(),
            )
        )

        with pytest.raises(ReviewError):
            ReviewService(None, ApprovalPolicy(minimum_approvals=1, require_unanimous=False))

        with pytest.raises(ReviewError):
            ReviewService(change_set_service, None)

        with pytest.raises(ReviewError):
            ReviewService(change_set_service, "not-a-policy")

    def test_reject_invalid_approval_policy(self):
        with pytest.raises(ReviewError):
            ApprovalPolicy(minimum_approvals=0, require_unanimous=False)

        with pytest.raises(ReviewError):
            ApprovalPolicy(minimum_approvals="two", require_unanimous=False)

        with pytest.raises(ReviewError):
            ApprovalPolicy(minimum_approvals=1, require_unanimous="yes")

    def test_status_none_when_not_submitted(self):
        _, review_service, change_set_id = _build()

        assert review_service.status(change_set_id) is None
