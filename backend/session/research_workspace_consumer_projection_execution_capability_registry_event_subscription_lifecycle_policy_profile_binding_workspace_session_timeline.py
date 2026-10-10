from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_audit_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuditError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_audit_event import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuditEvent,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionTimeline:
    """
    Immutable, point-in-time chronological view of every audit event
    recorded for a consumer projection execution capability registry
    event subscription lifecycle policy profile binding workspace
    execution session.

    The timeline is a value object only. It performs no recording or
    ordering. Assembling a session's timeline is the responsibility
    of a session audit service.

    Attributes:
        session_id: The identifier of the execution session this
            timeline concerns
        events: The session's audit events, in chronological order
    """

    session_id: str

    events: tuple[ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuditEvent, ...]

    def __post_init__(self):
        if self.session_id is None or not self.session_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuditError(
                "Cannot build a session timeline with an empty or blank session ID."
            )

        if self.events is None or not isinstance(self.events, tuple):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuditError(
                "Cannot build a session timeline with events that is not a tuple."
            )

        for event in self.events:
            if not isinstance(event, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuditEvent):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuditError(
                    "Cannot build a session timeline: every event must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuditEvent."
                )
