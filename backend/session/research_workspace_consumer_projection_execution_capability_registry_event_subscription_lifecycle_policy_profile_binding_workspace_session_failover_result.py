from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_scheduling_failover_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingFailoverError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionFailoverResult:
    """
    Immutable report of which execution worker a consumer projection
    execution capability registry event subscription lifecycle policy
    profile binding workspace execution session currently runs on.

    The result is a value object only. It performs no failover.
    Failing sessions over between workers and reporting their current
    placement is the responsibility of a session scheduling failover
    service.

    Attributes:
        reassigned: Whether the session is currently running on a
            backup worker rather than its plan's primary_worker
        worker_id: The execution worker the session currently runs on
    """

    reassigned: bool

    worker_id: str

    def __post_init__(self):
        if self.reassigned is None or not isinstance(self.reassigned, bool):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingFailoverError(
                "Cannot build a session failover result with a non-boolean reassigned."
            )

        if self.worker_id is None or not self.worker_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingFailoverError(
                "Cannot build a session failover result with an empty or blank worker ID."
            )
