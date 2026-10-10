from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_maintenance_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionMaintenanceError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionMaintenanceResult:
    """
    Immutable report of a consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    workspace session maintenance service's dispatch gate after a
    suspend() or resume() check.

    The result is a value object only. It performs no suspension.
    Suspending and resuming dispatch is the responsibility of a
    session maintenance service.

    Attributes:
        suspended: Whether dispatch is currently paused for
            maintenance
        resumed: Whether this check is what just lifted the pause;
            never True at the same time as suspended
    """

    suspended: bool

    resumed: bool

    def __post_init__(self):
        if self.suspended is None or not isinstance(self.suspended, bool):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionMaintenanceError(
                "Cannot build a session maintenance result with a non-boolean suspended."
            )

        if self.resumed is None or not isinstance(self.resumed, bool):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionMaintenanceError(
                "Cannot build a session maintenance result with a non-boolean resumed."
            )

        if self.suspended and self.resumed:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionMaintenanceError(
                "Cannot build a session maintenance result that is both suspended and resumed."
            )
