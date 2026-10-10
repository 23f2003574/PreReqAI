from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewStatus(
    str,
    Enum,
):
    """
    Canonical outcomes a single reviewer's review of a consumer
    projection execution capability registry event subscription
    lifecycle policy profile binding workspace change set can be in.

    This enum only names the possible outcomes. It performs no
    transition logic; a change set review service is responsible for
    enforcing which transitions are valid.

    PENDING is the only state a review may be approved or rejected
    from. APPROVED and REJECTED are terminal for that review; a
    reviewer whose review was rejected may submit a new review, which
    is tracked as a distinct review record rather than a mutation of
    the rejected one.
    """

    PENDING = "pending"

    APPROVED = "approved"

    REJECTED = "rejected"
