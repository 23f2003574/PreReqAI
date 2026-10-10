from dataclasses import (
    dataclass,
)

from datetime import datetime

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_attachment_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAttachmentError,
)

VALID_SESSION_ATTACHMENT_TYPES = (
    "report",
    "log",
    "export",
    "config",
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAttachment:
    """
    Immutable metadata record pointing at a runtime artifact — a
    report, log, export, or config — produced during a consumer
    projection execution capability registry event subscription
    lifecycle policy profile binding workspace execution session, so
    downstream stages can find it without the artifact's own payload
    ever being embedded in session state.

    The attachment is a value object only. It carries a location
    reference, not the artifact's contents, and performs no storage
    of its own. Attaching, retrieving, and detaching are the
    responsibility of a session attachment service.

    Attributes:
        attachment_id: The attachment's unique identifier
        session_id: The identifier of the execution session this
            attachment belongs to
        name: The attachment's human-readable name
        type: The kind of artifact this attachment points at, one of
            "report", "log", "export", or "config"
        location: Where the artifact itself can be found, such as a
            path or URI
        created_at: When this attachment was recorded
    """

    attachment_id: str

    session_id: str

    name: str

    type: str

    location: str

    created_at: datetime

    def __post_init__(self):
        if self.attachment_id is None or not self.attachment_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAttachmentError(
                "Cannot build a session attachment with an empty or blank attachment ID."
            )

        if self.session_id is None or not self.session_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAttachmentError(
                "Cannot build a session attachment with an empty or blank session ID."
            )

        if self.name is None or not self.name.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAttachmentError(
                "Cannot build a session attachment with an empty or blank name."
            )

        if self.type is None or not self.type.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAttachmentError(
                "Cannot build a session attachment with an empty or blank type."
            )

        if self.type not in VALID_SESSION_ATTACHMENT_TYPES:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAttachmentError(
                f"Invalid session attachment type {self.type!r}. Must be one of "
                f"{VALID_SESSION_ATTACHMENT_TYPES!r}."
            )

        if self.location is None or not self.location.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAttachmentError(
                "Cannot build a session attachment with an empty or blank location."
            )

        if self.created_at is None or not isinstance(self.created_at, datetime):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAttachmentError(
                "Cannot build a session attachment with a non-datetime created_at."
            )
