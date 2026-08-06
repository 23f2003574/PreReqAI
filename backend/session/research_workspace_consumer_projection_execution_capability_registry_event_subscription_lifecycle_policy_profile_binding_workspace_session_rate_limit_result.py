from dataclasses import (
    dataclass,
)

from datetime import datetime

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_rate_limit_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionRateLimitError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionRateLimitResult:
    """
    Immutable outcome of a consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    workspace execution session rate limit decision.

    The result is a value object only. It performs no counting or
    enforcement. Producing this outcome is the responsibility of a
    session rate limit service.

    Attributes:
        allowed: Whether the request is, or was, within the
            applicable limit
        remaining: How many further requests may still be made within
            the current sliding window
        reset_at: When the oldest request counted against the current
            window ages out, freeing up a slot
    """

    allowed: bool

    remaining: int

    reset_at: datetime

    def __post_init__(self):
        if self.allowed is None or not isinstance(self.allowed, bool):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionRateLimitError(
                "Cannot build a rate limit result with a non-boolean allowed."
            )

        if (
            self.remaining is None
            or isinstance(self.remaining, bool)
            or not isinstance(self.remaining, int)
            or self.remaining < 0
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionRateLimitError(
                f"Invalid rate limit result remaining {self.remaining!r}; remaining must be a non-negative integer."
            )

        if self.reset_at is None or not isinstance(self.reset_at, datetime):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionRateLimitError(
                "Cannot build a rate limit result with a non-datetime reset_at."
            )
