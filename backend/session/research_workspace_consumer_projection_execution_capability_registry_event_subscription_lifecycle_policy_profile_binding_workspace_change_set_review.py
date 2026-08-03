from dataclasses import (
    dataclass,
)

from datetime import datetime

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_change_set_review_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_change_set_review_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewStatus,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReview:
    """
    Immutable record of a single reviewer's review of a consumer
    projection execution capability registry event subscription
    lifecycle policy profile binding workspace change set.

    The review is a value object only. It performs no submission,
    approval, or rejection. Those are the responsibility of a binding
    workspace change set review service, which produces a new review
    record for every transition rather than mutating an existing one.

    Attributes:
        review_id: The review's unique identifier
        change_set_id: The identifier of the change set the review
            concerns
        reviewer: The identifier of the reviewer who submitted the
            review
        status: The review's current outcome (one of "pending",
            "approved", or "rejected")
        comments: The reviewer's comments, or None if none were given
        reviewed_at: When the review was approved or rejected, or
            None if it is still pending
    """

    review_id: str

    change_set_id: str

    reviewer: str

    status: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewStatus

    comments: str | None

    reviewed_at: datetime | None

    def __post_init__(self):
        if self.review_id is None or not self.review_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewError(
                "Cannot build a change set review with an empty or blank review ID."
            )

        if self.change_set_id is None or not self.change_set_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewError(
                "Cannot build a change set review with an empty or blank change set ID."
            )

        if self.reviewer is None or not self.reviewer.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewError(
                "Cannot build a change set review with an empty or blank reviewer."
            )

        if not isinstance(
            self.status,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewStatus,
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewError(
                "Cannot build a change set review: status must be a "
                "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewStatus."
            )

        if self.comments is not None and not isinstance(self.comments, str):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewError(
                "Cannot build a change set review with comments that are not a string."
            )

        is_pending = (
            self.status
            == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewStatus.PENDING
        )

        if is_pending and self.reviewed_at is not None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewError(
                "Cannot build a change set review: a pending review cannot have a reviewed_at."
            )

        if not is_pending and self.reviewed_at is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewError(
                "Cannot build a change set review: an approved or rejected review must have a reviewed_at."
            )
