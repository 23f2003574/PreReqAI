from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_execution_session_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionResult:
    """
    Immutable outcome of finishing a consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding workspace execution session.

    The result is a value object only. It performs no lifecycle
    transitions. Finishing a session is the responsibility of an
    execution session service.

    Attributes:
        session_id: The identifier of the session this result
            concerns
        successful: Whether the pipeline run the session tracked
            finished successfully
    """

    session_id: str

    successful: bool

    def __post_init__(self):
        if self.session_id is None or not self.session_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionError(
                "Cannot build an execution session result with an empty or blank session ID."
            )

        if self.successful is None or not isinstance(self.successful, bool):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionError(
                "Cannot build an execution session result with a non-boolean successful."
            )
