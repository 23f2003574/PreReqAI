from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_policy_simulation_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicySimulationError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicySimulation:
    """
    Immutable record describing a single read-only simulation of a
    consumer projection execution capability registry event
    subscription lifecycle policy profile binding workspace execution
    session policy version's impact, run against a specific set of
    sessions without changing any of their real, runtime-governing
    state.

    The simulation is a value object only. It performs no evaluation.
    Running, reporting on, and discarding simulations are the
    responsibility of a session policy simulation service.

    Attributes:
        simulation_id: The simulation's unique identifier
        policy_id: The identifier of the policy this simulation
            concerns
        target_version: The version number of policy_id this
            simulation evaluated sessions against
        session_ids: The sessions this simulation evaluated
    """

    simulation_id: str

    policy_id: str

    target_version: int

    session_ids: tuple[str, ...]

    def __post_init__(self):
        if self.simulation_id is None or not self.simulation_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicySimulationError(
                "Cannot build a session policy simulation with an empty or blank simulation ID."
            )

        if self.policy_id is None or not self.policy_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicySimulationError(
                "Cannot build a session policy simulation with an empty or blank policy ID."
            )

        if (
            self.target_version is None
            or isinstance(self.target_version, bool)
            or not isinstance(self.target_version, int)
            or self.target_version <= 0
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicySimulationError(
                f"Invalid session policy simulation target_version {self.target_version!r}; target_version must "
                "be a positive integer."
            )

        if self.session_ids is None or not isinstance(self.session_ids, tuple):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicySimulationError(
                "Cannot build a session policy simulation with session_ids that is not a tuple."
            )

        for session_id in self.session_ids:
            if session_id is None or not isinstance(session_id, str) or not session_id.strip():
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicySimulationError(
                    "Cannot build a session policy simulation with an empty, blank, or non-string session ID."
                )
