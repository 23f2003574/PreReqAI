from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_conflict_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceConflictError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_conflict_resolution_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceConflictResolutionStatus,
)

_VALID_CONFLICT_TYPES = (
    "stale_state",
    "concurrent_edit",
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeConflict:
    """
    Immutable record of a single resource-level conflict detected on
    a consumer projection execution capability registry event
    subscription lifecycle policy profile binding workspace change
    set.

    The conflict is a value object only. It performs no detection or
    resolution. Those are the responsibility of a binding workspace
    conflict service, which produces a new conflict record for every
    transition rather than mutating an existing one.

    Attributes:
        conflict_id: The conflict's unique identifier
        change_set_id: The identifier of the change set the conflict
            was detected on
        resource_id: The identifier of the member resource the
            conflict concerns
        conflict_type: The kind of conflict detected (one of
            "stale_state", where a staged operation no longer matches
            the workspace's current state, or "concurrent_edit",
            where another open change set also stages an operation
            against the same resource)
        resolution_status: The conflict's current resolution state
    """

    conflict_id: str

    change_set_id: str

    resource_id: str

    conflict_type: str

    resolution_status: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceConflictResolutionStatus

    def __post_init__(self):
        if self.conflict_id is None or not self.conflict_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceConflictError(
                "Cannot build a change conflict with an empty or blank conflict ID."
            )

        if self.change_set_id is None or not self.change_set_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceConflictError(
                "Cannot build a change conflict with an empty or blank change set ID."
            )

        if self.resource_id is None or not self.resource_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceConflictError(
                "Cannot build a change conflict with an empty or blank resource ID."
            )

        if self.conflict_type is None or not self.conflict_type.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceConflictError(
                "Cannot build a change conflict with an empty or blank conflict type."
            )

        if self.conflict_type not in _VALID_CONFLICT_TYPES:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceConflictError(
                f"Invalid change conflict type {self.conflict_type!r}. Must be one of {_VALID_CONFLICT_TYPES!r}."
            )

        if not isinstance(
            self.resolution_status,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceConflictResolutionStatus,
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceConflictError(
                "Cannot build a change conflict: resolution_status must be a "
                "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceConflictResolutionStatus."
            )
