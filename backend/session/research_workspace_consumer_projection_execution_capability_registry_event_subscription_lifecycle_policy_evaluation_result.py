from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_evaluation_request import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationRequest,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationResult:
    """
    Immutable outcome produced after evaluating a lifecycle policy
    against a proposed lifecycle transition.

    The result is a value object only. It performs no evaluation of
    the transition against the policy, no validation of the
    transition, and no execution of lifecycle changes.

    Attributes:
        request: The evaluation request this result was produced for
        approved: Whether the transition complies with the policy
        rejection_reason: The reason the transition was rejected, or
            None if approved
    """

    request: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationRequest
    )

    approved: bool

    rejection_reason: (
        str | None
    )
