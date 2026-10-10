from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_scheduling_balancer_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingBalancerError,
)

VALID_SESSION_SCHEDULING_BALANCER_ALGORITHMS = frozenset(
    {
        "least_loaded",
        "round_robin",
    }
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingStrategy:
    """
    Immutable, configured algorithm a consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding workspace session scheduling balancer service may use to
    distribute sessions across execution workers.

    The strategy is a value object only. It performs no assignment.
    Selecting the active strategy and assigning sessions is the
    responsibility of a session scheduling balancer service.

    Attributes:
        strategy_id: The strategy's unique identifier
        algorithm: The balancing algorithm this strategy names; one
            of "least_loaded" or "round_robin"
        enabled: Whether this is the strategy currently in effect;
            exactly one configured strategy must be enabled
    """

    strategy_id: str

    algorithm: str

    enabled: bool

    def __post_init__(self):
        if self.strategy_id is None or not self.strategy_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingBalancerError(
                "Cannot build a session scheduling strategy with an empty or blank strategy ID."
            )

        if self.algorithm not in VALID_SESSION_SCHEDULING_BALANCER_ALGORITHMS:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingBalancerError(
                f"Cannot build a session scheduling strategy with unknown algorithm {self.algorithm!r}; expected "
                f"one of {sorted(VALID_SESSION_SCHEDULING_BALANCER_ALGORITHMS)}."
            )

        if self.enabled is None or not isinstance(self.enabled, bool):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingBalancerError(
                "Cannot build a session scheduling strategy with a non-boolean enabled."
            )
