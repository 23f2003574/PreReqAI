from dataclasses import (
    dataclass,
)

from datetime import datetime

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_heartbeat_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionHeartbeatError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionHeartbeat:
    """
    Immutable record of a single liveness signal sent by a consumer
    projection execution capability registry event subscription
    lifecycle policy profile binding workspace execution session
    while it runs, so a monitor can tell it is still making progress.

    The heartbeat is a value object only. It performs no staleness
    detection or recovery. Recording heartbeats and deciding whether
    a session is stale are the responsibility of a session heartbeat
    service.

    Attributes:
        session_id: The identifier of the execution session this
            heartbeat was sent by
        sequence: This heartbeat's position in its session's
            monotonically increasing heartbeat sequence
        recorded_at: When this heartbeat was recorded
    """

    session_id: str

    sequence: int

    recorded_at: datetime

    def __post_init__(self):
        if self.session_id is None or not self.session_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionHeartbeatError(
                "Cannot build a session heartbeat with an empty or blank session ID."
            )

        if self.sequence is None or isinstance(self.sequence, bool) or not isinstance(self.sequence, int):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionHeartbeatError(
                "Cannot build a session heartbeat with a non-integer sequence."
            )

        if self.sequence < 0:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionHeartbeatError(
                "Cannot build a session heartbeat with a negative sequence."
            )

        if self.recorded_at is None or not isinstance(self.recorded_at, datetime):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionHeartbeatError(
                "Cannot build a session heartbeat with a non-datetime recorded_at."
            )
