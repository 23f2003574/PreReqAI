from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_policy_rollout_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyRolloutError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyRolloutResult:
    """
    Immutable outcome of resolving a consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding workspace execution session against whichever rollout, if
    any, currently governs its policy.

    The result is a value object only. It performs no resolution.
    Producing this outcome is the responsibility of a session policy
    rollout service.

    Attributes:
        applied: Whether the active rollout's target version was
            adopted for this session
        assigned_version: The version number the session was actually
            resolved to, whether or not a rollout was applied
    """

    applied: bool

    assigned_version: int

    def __post_init__(self):
        if self.applied is None or not isinstance(self.applied, bool):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyRolloutError(
                "Cannot build a session policy rollout result with a non-boolean applied."
            )

        if (
            self.assigned_version is None
            or isinstance(self.assigned_version, bool)
            or not isinstance(self.assigned_version, int)
            or self.assigned_version <= 0
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyRolloutError(
                f"Invalid session policy rollout result assigned_version {self.assigned_version!r}; "
                "assigned_version must be a positive integer."
            )
