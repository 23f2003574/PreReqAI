from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_cleanup_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCleanupError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCleanupPolicy:
    """
    Immutable configuration describing when a consumer projection
    execution capability registry event subscription lifecycle policy
    profile binding workspace execution session is stale enough to be
    retired, and how it should be retired.

    The policy is a value object only. It performs no scanning or
    retirement. Applying a policy against sessions is the
    responsibility of a session cleanup service.

    Attributes:
        policy_id: The policy's unique identifier
        max_age: How old, in seconds, an eligible session's relevant
            timestamp must be before it is considered stale
        completed_only: When True, only sessions that finished
            successfully are eligible; sessions that were cancelled
            are left alone. A session still active is never eligible,
            regardless of this flag
        archive_before_delete: When True, an eligible session is
            archived before it is retired
    """

    policy_id: str

    max_age: float

    completed_only: bool

    archive_before_delete: bool

    def __post_init__(self):
        if self.policy_id is None or not self.policy_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCleanupError(
                "Cannot build a session cleanup policy with an empty or blank policy ID."
            )

        if (
            self.max_age is None
            or isinstance(self.max_age, bool)
            or not isinstance(self.max_age, (int, float))
            or self.max_age <= 0
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCleanupError(
                f"Invalid session cleanup policy retention period {self.max_age!r}; max_age must be a positive "
                "number of seconds."
            )

        if self.completed_only is None or not isinstance(self.completed_only, bool):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCleanupError(
                "Cannot build a session cleanup policy with a non-boolean completed_only."
            )

        if self.archive_before_delete is None or not isinstance(self.archive_before_delete, bool):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCleanupError(
                "Cannot build a session cleanup policy with a non-boolean archive_before_delete."
            )
