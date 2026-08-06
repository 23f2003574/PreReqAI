from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_execution_session_policy_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionPolicyError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionPolicyAssignment:
    """
    Immutable record binding a single consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding workspace execution session to the one reusable session
    policy currently governing it.

    The assignment is a value object only. It performs no lookup or
    enforcement. Creating, replacing, and removing assignments are the
    responsibility of a session policy service.

    Attributes:
        session_id: The identifier of the execution session this
            assignment concerns
        policy_id: The identifier of the session policy governing
            this session
    """

    session_id: str

    policy_id: str

    def __post_init__(self):
        if self.session_id is None or not self.session_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionPolicyError(
                "Cannot build a session policy assignment with an empty or blank session ID."
            )

        if self.policy_id is None or not self.policy_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionPolicyError(
                "Cannot build a session policy assignment with an empty or blank policy ID."
            )
