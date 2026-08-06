from dataclasses import (
    dataclass,
)

from datetime import datetime

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_admission_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAdmissionError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAdmissionRequest:
    """
    Immutable request asking whether a consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding workspace execution session may start.

    The request is a value object only. It performs no admission
    decision. Deciding whether a session may start is the
    responsibility of a session admission service.

    Attributes:
        session_id: The identifier of the session asking to start
        policy_id: The identifier of the policy the requester believes
            governs this session
        requested_at: When this admission request was made
    """

    session_id: str

    policy_id: str

    requested_at: datetime

    def __post_init__(self):
        if self.session_id is None or not self.session_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAdmissionError(
                "Cannot build an admission request with an empty or blank session ID."
            )

        if self.policy_id is None or not self.policy_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAdmissionError(
                "Cannot build an admission request with an empty or blank policy ID."
            )

        if self.requested_at is None or not isinstance(self.requested_at, datetime):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAdmissionError(
                "Cannot build an admission request with a non-datetime requested_at."
            )
