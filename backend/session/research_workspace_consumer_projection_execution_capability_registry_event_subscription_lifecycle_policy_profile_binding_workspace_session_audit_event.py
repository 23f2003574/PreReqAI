from dataclasses import (
    dataclass,
    field,
)

from datetime import datetime

from types import MappingProxyType

from typing import Mapping

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_audit_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuditError,
)

VALID_SESSION_AUDIT_EVENT_TYPES = (
    "START",
    "FINISH",
    "CANCEL",
    "RESTORE",
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuditEvent:
    """
    Immutable record of a single lifecycle occurrence on a consumer
    projection execution capability registry event subscription
    lifecycle policy profile binding workspace execution session,
    kept for diagnostics, compliance, and replay.

    The audit event is a value object only. It performs no recording
    or retention. Recording, retrieving, and purging audit events are
    the responsibility of a session audit service.

    Attributes:
        event_id: The event's unique identifier
        session_id: The identifier of the execution session this
            event concerns
        event_type: The kind of lifecycle occurrence, one of "START",
            "FINISH", "CANCEL", or "RESTORE"
        actor: The identifier of whoever or whatever caused this event
        timestamp: When this event occurred
        metadata: Additional context captured with this event, empty
            if none applies
    """

    event_id: str

    session_id: str

    event_type: str

    actor: str

    timestamp: datetime

    metadata: Mapping = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self):
        if self.event_id is None or not self.event_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuditError(
                "Cannot build a session audit event with an empty or blank event ID."
            )

        if self.session_id is None or not self.session_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuditError(
                "Cannot build a session audit event with an empty or blank session ID."
            )

        if self.event_type is None or not isinstance(self.event_type, str) or not self.event_type.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuditError(
                "Cannot build a session audit event with an empty, blank, or non-string event_type."
            )

        if self.event_type not in VALID_SESSION_AUDIT_EVENT_TYPES:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuditError(
                f"Invalid session audit event_type {self.event_type!r}. Must be one of "
                f"{VALID_SESSION_AUDIT_EVENT_TYPES!r}."
            )

        if self.actor is None or not self.actor.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuditError(
                "Cannot build a session audit event with an empty or blank actor."
            )

        if self.timestamp is None or not isinstance(self.timestamp, datetime):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuditError(
                "Cannot build a session audit event with a non-datetime timestamp."
            )

        if self.metadata is None or not isinstance(self.metadata, Mapping):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuditError(
                "Cannot build a session audit event with metadata that is not a mapping."
            )
