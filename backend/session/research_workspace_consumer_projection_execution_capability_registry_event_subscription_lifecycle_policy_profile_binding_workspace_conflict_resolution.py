from dataclasses import (
    dataclass,
)

from datetime import datetime

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_conflict_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceConflictError,
)

_VALID_STRATEGIES = (
    "manual",
    "auto",
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceConflictResolution:
    """
    Immutable record of how a single consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding workspace change conflict was resolved.

    The resolution is a value object only. It performs no resolving.
    Resolving a conflict, and producing its resolution record, is the
    responsibility of a binding workspace conflict service.

    Attributes:
        conflict_id: The identifier of the conflict that was resolved
        strategy: The strategy used to resolve the conflict (one of
            "manual", where a human explicitly accepted the current
            state, or "auto", where the service resolved it
            automatically)
        resolved_at: When the conflict was resolved
    """

    conflict_id: str

    strategy: str

    resolved_at: datetime

    def __post_init__(self):
        if self.conflict_id is None or not self.conflict_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceConflictError(
                "Cannot build a conflict resolution with an empty or blank conflict ID."
            )

        if self.strategy is None or not self.strategy.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceConflictError(
                "Cannot build a conflict resolution with an empty or blank strategy."
            )

        if self.strategy not in _VALID_STRATEGIES:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceConflictError(
                f"Invalid conflict resolution strategy {self.strategy!r}. Must be one of {_VALID_STRATEGIES!r}."
            )

        if self.resolved_at is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceConflictError(
                "Cannot build a conflict resolution with a None resolved_at."
            )
