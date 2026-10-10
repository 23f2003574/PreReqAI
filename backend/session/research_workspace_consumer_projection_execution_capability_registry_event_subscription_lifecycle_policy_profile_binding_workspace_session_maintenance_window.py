from dataclasses import (
    dataclass,
)

from datetime import datetime

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_maintenance_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionMaintenanceError,
)

GLOBAL_MAINTENANCE_SCOPE = "global"


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionMaintenanceWindow:
    """
    Immutable period during which consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding workspace session dispatch is paused for maintenance.

    The window is a value object only. It performs no suspension.
    Enabling, disabling, suspending, and resuming dispatch around
    maintenance windows is the responsibility of a session maintenance
    service.

    Attributes:
        window_id: The window's unique identifier
        starts_at: When this maintenance window opens
        ends_at: When this maintenance window closes, strictly after
            starts_at
        scope: What this window applies to. The special value
            "global" pauses dispatch for everything; any other value
            names a narrower scope, such as a specific worker or
            pipeline, that is tracked and reported but does not pause
            dispatch on its own
    """

    window_id: str

    starts_at: datetime

    ends_at: datetime

    scope: str

    def __post_init__(self):
        if self.window_id is None or not self.window_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionMaintenanceError(
                "Cannot build a session maintenance window with an empty or blank window ID."
            )

        if self.starts_at is None or not isinstance(self.starts_at, datetime) or self.starts_at.utcoffset() is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionMaintenanceError(
                "Cannot build a session maintenance window with a non-timezone-aware starts_at."
            )

        if self.ends_at is None or not isinstance(self.ends_at, datetime) or self.ends_at.utcoffset() is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionMaintenanceError(
                "Cannot build a session maintenance window with a non-timezone-aware ends_at."
            )

        if self.ends_at <= self.starts_at:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionMaintenanceError(
                "Cannot build a session maintenance window with ends_at at or before starts_at."
            )

        if self.scope is None or not self.scope.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionMaintenanceError(
                "Cannot build a session maintenance window with an empty or blank scope."
            )
