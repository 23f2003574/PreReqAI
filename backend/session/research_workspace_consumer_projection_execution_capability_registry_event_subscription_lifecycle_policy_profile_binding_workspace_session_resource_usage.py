from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_resource_governance_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionResourceGovernanceError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionResourceUsage:
    """
    Immutable, point-in-time snapshot of how much CPU, memory, and
    storage a single consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    workspace execution session currently has allocated.

    The usage is a value object only. It performs no allocation or
    tracking. Producing this snapshot is the responsibility of a
    session resource governance service.

    Attributes:
        session_id: The identifier of the session this usage concerns
        cpu_used: How much CPU the session currently has allocated
        memory_used: How much memory the session currently has
            allocated
        storage_used: How much storage the session currently has
            allocated
    """

    session_id: str

    cpu_used: float

    memory_used: float

    storage_used: float

    def __post_init__(self):
        if self.session_id is None or not self.session_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionResourceGovernanceError(
                "Cannot build a session resource usage with an empty or blank session ID."
            )

        for value, label in (
            (self.cpu_used, "cpu_used"),
            (self.memory_used, "memory_used"),
            (self.storage_used, "storage_used"),
        ):
            if value is None or isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionResourceGovernanceError(
                    f"Invalid session resource usage {label} {value!r}; {label} must be a non-negative number."
                )
