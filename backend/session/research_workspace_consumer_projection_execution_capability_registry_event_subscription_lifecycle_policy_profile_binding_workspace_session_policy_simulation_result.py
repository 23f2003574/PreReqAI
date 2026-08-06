from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_policy_simulation_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicySimulationError,
)


def _validate_session_id_tuple(value, label):
    if value is None or not isinstance(value, tuple):
        raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicySimulationError(
            f"Cannot build a session policy simulation result with {label} that is not a tuple."
        )

    for session_id in value:
        if session_id is None or not isinstance(session_id, str) or not session_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicySimulationError(
                f"Cannot build a session policy simulation result with an empty, blank, or non-string ID in "
                f"{label}."
            )


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicySimulationResult:
    """
    Immutable outcome of a consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    workspace execution session policy simulation, partitioning every
    evaluated session into those that would pass and those that would
    fail under the simulated version.

    The result is a value object only. It performs no evaluation.
    Producing this outcome is the responsibility of a session policy
    simulation service.

    Attributes:
        affected: Every session the simulation evaluated
        passed: The sessions, among affected, that would pass under
            the simulated version
        failed: The sessions, among affected, that would fail under
            the simulated version
    """

    affected: tuple[str, ...]

    passed: tuple[str, ...]

    failed: tuple[str, ...]

    def __post_init__(self):
        _validate_session_id_tuple(self.affected, "affected")
        _validate_session_id_tuple(self.passed, "passed")
        _validate_session_id_tuple(self.failed, "failed")

        if set(self.passed) & set(self.failed):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicySimulationError(
                "Cannot build a session policy simulation result where a session is both passed and failed."
            )

        if set(self.passed) | set(self.failed) != set(self.affected):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicySimulationError(
                "Cannot build a session policy simulation result where passed and failed do not together account "
                "for exactly affected."
            )
