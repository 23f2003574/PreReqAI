from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_attachment_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAttachmentError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAttachmentResult:
    """
    Immutable outcome of attaching a runtime artifact to a consumer
    projection execution capability registry event subscription
    lifecycle policy profile binding workspace execution session.

    The result is a value object only. It performs no attachment.
    Attaching is the responsibility of a session attachment service.

    Attributes:
        attachment_id: The identifier of the attachment this result
            concerns
        attached: Whether the attachment succeeded
    """

    attachment_id: str

    attached: bool

    def __post_init__(self):
        if self.attachment_id is None or not self.attachment_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAttachmentError(
                "Cannot build a session attachment result with an empty or blank attachment ID."
            )

        if self.attached is None or not isinstance(self.attached, bool):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAttachmentError(
                "Cannot build a session attachment result with a non-boolean attached."
            )
