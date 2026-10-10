from dataclasses import (
    dataclass,
)

from datetime import datetime

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_scheduling_audit_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingAuditError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingAuditEvent:
    """
    Immutable record of a single decision the scheduler made about a
    consumer projection execution capability registry event
    subscription lifecycle policy profile binding workspace session
    schedule, so the full sequence of decisions can later be
    inspected or deterministically replayed for diagnostics.

    The event is a value object only. It performs no replay.
    Recording, retrieving, and replaying audit events is the
    responsibility of a session scheduling audit service.

    Attributes:
        event_id: The event's unique identifier
        schedule_id: The identifier of the schedule this event
            concerns
        event_type: The kind of decision this event records, such as
            "scheduled", "dispatched", or "cancelled"
        timestamp: When the scheduler made this decision
        metadata: Additional context about the decision, keyed by
            non-blank string field names
    """

    event_id: str

    schedule_id: str

    event_type: str

    timestamp: datetime

    metadata: dict

    def __post_init__(self):
        if self.event_id is None or not self.event_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingAuditError(
                "Cannot build a session scheduling audit event with an empty or blank event ID."
            )

        if self.schedule_id is None or not self.schedule_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingAuditError(
                "Cannot build a session scheduling audit event with an empty or blank schedule ID."
            )

        if self.event_type is None or not self.event_type.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingAuditError(
                "Cannot build a session scheduling audit event with an empty or blank event_type."
            )

        if self.timestamp is None or not isinstance(self.timestamp, datetime) or self.timestamp.utcoffset() is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingAuditError(
                "Cannot build a session scheduling audit event with a non-timezone-aware timestamp."
            )

        if not isinstance(self.metadata, dict) or any(
            key is None or not isinstance(key, str) or not key.strip() for key in self.metadata.keys()
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingAuditError(
                "Cannot build a session scheduling audit event with metadata that is not a dict of non-blank "
                "string keys."
            )
