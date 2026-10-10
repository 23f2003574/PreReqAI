from dataclasses import (
    dataclass,
)

from datetime import datetime

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_heartbeat_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionHeartbeatError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionHeartbeatStatus:
    """
    Immutable, point-in-time liveness assessment of a consumer
    projection execution capability registry event subscription
    lifecycle policy profile binding workspace execution session,
    derived from its heartbeat history.

    The status is a value object only. It performs no assessment.
    Deciding whether a session is healthy is the responsibility of a
    session heartbeat service.

    Attributes:
        session_id: The identifier of the execution session this
            status concerns
        healthy: Whether the session is currently considered live
        last_seen: When the session's most recent heartbeat was
            recorded, or None if it has never sent one
    """

    session_id: str

    healthy: bool

    last_seen: datetime = None

    def __post_init__(self):
        if self.session_id is None or not self.session_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionHeartbeatError(
                "Cannot build a session heartbeat status with an empty or blank session ID."
            )

        if self.healthy is None or not isinstance(self.healthy, bool):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionHeartbeatError(
                "Cannot build a session heartbeat status with a non-boolean healthy."
            )

        if self.last_seen is not None and not isinstance(self.last_seen, datetime):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionHeartbeatError(
                "Cannot build a session heartbeat status with a non-datetime last_seen."
            )
