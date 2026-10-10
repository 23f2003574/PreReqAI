from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_priority_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPriorityError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPriority:
    """
    Immutable base priority a consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding workspace execution session was assigned, so ready
    sessions can be ordered against one another for execution.

    The priority is a value object only. It performs no ordering or
    aging. Assigning sessions, applying aging, and selecting the next
    session to execute is the responsibility of a session priority
    service.

    Attributes:
        session_id: The identifier of the execution session this
            priority applies to
        priority: The session's base priority; a higher value
            executes before a lower one
        aging_enabled: Whether this session's effective priority
            should increase the longer it waits, so it is never
            starved by a steady stream of higher-priority arrivals
    """

    session_id: str

    priority: int

    aging_enabled: bool

    def __post_init__(self):
        if self.session_id is None or not self.session_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPriorityError(
                "Cannot build a session priority with an empty or blank session ID."
            )

        if self.priority is None or isinstance(self.priority, bool) or not isinstance(self.priority, int):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPriorityError(
                "Cannot build a session priority with a non-integer priority."
            )

        if self.priority < 0:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPriorityError(
                "Cannot build a session priority with a negative priority."
            )

        if self.aging_enabled is None or not isinstance(self.aging_enabled, bool):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPriorityError(
                "Cannot build a session priority with a non-boolean aging_enabled."
            )
