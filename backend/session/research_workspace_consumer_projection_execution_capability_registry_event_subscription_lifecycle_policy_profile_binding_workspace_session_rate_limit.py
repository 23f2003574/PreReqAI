from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_permission import (
    VALID_SESSION_OPERATIONS,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_rate_limit_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionRateLimitError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionRateLimit:
    """
    Immutable configuration capping how many times a single consumer
    projection execution capability registry event subscription
    lifecycle policy profile binding workspace execution session may
    invoke a specific lifecycle operation within a sliding time
    window.

    The rate limit is a value object only. It performs no counting or
    enforcement. Checking, recording, and resetting request counts
    against a limit are the responsibility of a session rate limit
    service.

    Attributes:
        limit_id: The limit's unique identifier
        operation: The lifecycle operation this limit governs, one of
            "START", "FINISH", "CANCEL", or "RESTORE"
        max_requests: How many requests for operation a single session
            may make within window_seconds
        window_seconds: The length, in seconds, of the sliding window
            over which max_requests is enforced
    """

    limit_id: str

    operation: str

    max_requests: int

    window_seconds: float

    def __post_init__(self):
        if self.limit_id is None or not self.limit_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionRateLimitError(
                "Cannot build a session rate limit with an empty or blank limit ID."
            )

        if self.operation is None or not isinstance(self.operation, str) or not self.operation.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionRateLimitError(
                "Cannot build a session rate limit with an empty, blank, or non-string operation."
            )

        if self.operation not in VALID_SESSION_OPERATIONS:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionRateLimitError(
                f"Invalid session rate limit operation {self.operation!r}. Must be one of "
                f"{VALID_SESSION_OPERATIONS!r}."
            )

        if (
            self.max_requests is None
            or isinstance(self.max_requests, bool)
            or not isinstance(self.max_requests, int)
            or self.max_requests <= 0
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionRateLimitError(
                f"Invalid session rate limit max_requests {self.max_requests!r}; max_requests must be a positive "
                "integer."
            )

        if (
            self.window_seconds is None
            or isinstance(self.window_seconds, bool)
            or not isinstance(self.window_seconds, (int, float))
            or self.window_seconds <= 0
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionRateLimitError(
                f"Invalid session rate limit window_seconds {self.window_seconds!r}; window_seconds must be a "
                "positive number of seconds."
            )
