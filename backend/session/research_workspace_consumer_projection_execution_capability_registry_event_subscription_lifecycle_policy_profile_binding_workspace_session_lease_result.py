from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_lease_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLeaseError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLeaseResult:
    """
    Immutable report of a consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    workspace session lease's activity state after it was released,
    whether explicitly or through automatic expiry.

    The result is a value object only. It performs no release.
    Releasing a lease, explicitly or through automatic expiry, is the
    responsibility of a session lease service.

    Attributes:
        lease_id: The identifier of the lease this result concerns
        active: Whether the lease is still active; False for every
            result a session lease service currently produces, since
            it only reports on leases that have just been released
    """

    lease_id: str

    active: bool

    def __post_init__(self):
        if self.lease_id is None or not self.lease_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLeaseError(
                "Cannot build a session lease result with an empty or blank lease ID."
            )

        if self.active is None or not isinstance(self.active, bool):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLeaseError(
                "Cannot build a session lease result with a non-boolean active."
            )
