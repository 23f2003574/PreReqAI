from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_policy_version_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyVersionError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyResolution:
    """
    Immutable record binding a single consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding workspace execution session to the specific policy
    version it was created against, so a policy published after the
    session started never changes what governs it.

    The resolution is a value object only. It performs no lookup or
    binding. Resolving and retaining a session's bound version are the
    responsibility of a session policy version service.

    Attributes:
        session_id: The identifier of the session this resolution was
            made for
        policy_id: The identifier of the policy governing the session
        version: The specific version number of policy_id the session
            is bound to
    """

    session_id: str

    policy_id: str

    version: int

    def __post_init__(self):
        if self.session_id is None or not self.session_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyVersionError(
                "Cannot build a session policy resolution with an empty or blank session ID."
            )

        if self.policy_id is None or not self.policy_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyVersionError(
                "Cannot build a session policy resolution with an empty or blank policy ID."
            )

        if (
            self.version is None
            or isinstance(self.version, bool)
            or not isinstance(self.version, int)
            or self.version <= 0
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyVersionError(
                f"Invalid session policy resolution version {self.version!r}; version must be a positive integer."
            )
