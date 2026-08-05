from dataclasses import (
    dataclass,
)

from datetime import datetime

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_lease_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLeaseError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLease:
    """
    Immutable time-boxed claim held by a worker on a consumer
    projection execution capability registry event subscription
    lifecycle policy profile binding workspace execution session, so
    an abandoned or disconnected worker's claim lapses on its own
    instead of blocking the session forever.

    The lease is a value object only. It performs no expiry
    enforcement. Acquiring, renewing, and releasing leases are the
    responsibility of a session lease service.

    Attributes:
        lease_id: The lease's unique identifier
        session_id: The identifier of the execution session this
            lease is held against
        holder_id: The identifier of the worker holding this lease
        acquired_at: When this lease was first acquired
        expires_at: When this lease lapses if not renewed or released
            first
    """

    lease_id: str

    session_id: str

    holder_id: str

    acquired_at: datetime

    expires_at: datetime

    def __post_init__(self):
        if self.lease_id is None or not self.lease_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLeaseError(
                "Cannot build a session lease with an empty or blank lease ID."
            )

        if self.session_id is None or not self.session_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLeaseError(
                "Cannot build a session lease with an empty or blank session ID."
            )

        if self.holder_id is None or not self.holder_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLeaseError(
                "Cannot build a session lease with an empty or blank holder ID."
            )

        if self.acquired_at is None or not isinstance(self.acquired_at, datetime):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLeaseError(
                "Cannot build a session lease with a non-datetime acquired_at."
            )

        if self.expires_at is None or not isinstance(self.expires_at, datetime):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLeaseError(
                "Cannot build a session lease with a non-datetime expires_at."
            )

        if self.expires_at <= self.acquired_at:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLeaseError(
                "Cannot build a session lease with expires_at at or before acquired_at."
            )
