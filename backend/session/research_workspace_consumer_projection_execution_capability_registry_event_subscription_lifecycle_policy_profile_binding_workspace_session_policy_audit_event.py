from dataclasses import (
    dataclass,
)

from datetime import datetime

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_policy_audit_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyAuditError,
)

VALID_SESSION_POLICY_AUDIT_EVENT_TYPES = (
    "RESOLVED",
    "COMPLIANT",
    "DRIFT_DETECTED",
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyAuditEvent:
    """
    Immutable, append-only audit log entry recording something that
    happened during a consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    workspace execution session's policy evaluation.

    The event is a value object only. It performs no recording or
    drift detection. Recording, retrieving, and purging events, and
    detecting drift, are the responsibility of a session policy audit
    service.

    Attributes:
        event_id: The event's unique identifier
        session_id: The identifier of the session this event concerns
        policy_id: The identifier of the policy in effect when this
            event occurred
        version: The version number of policy_id in effect when this
            event occurred
        event_type: What kind of event this is, one of "RESOLVED",
            "COMPLIANT", or "DRIFT_DETECTED"
        timestamp: When this event occurred
    """

    event_id: str

    session_id: str

    policy_id: str

    version: int

    event_type: str

    timestamp: datetime

    def __post_init__(self):
        if self.event_id is None or not self.event_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyAuditError(
                "Cannot build a session policy audit event with an empty or blank event ID."
            )

        if self.session_id is None or not self.session_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyAuditError(
                "Cannot build a session policy audit event with an empty or blank session ID."
            )

        if self.policy_id is None or not self.policy_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyAuditError(
                "Cannot build a session policy audit event with an empty or blank policy ID."
            )

        if (
            self.version is None
            or isinstance(self.version, bool)
            or not isinstance(self.version, int)
            or self.version <= 0
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyAuditError(
                f"Invalid session policy audit event version {self.version!r}; version must be a positive "
                "integer."
            )

        if self.event_type not in VALID_SESSION_POLICY_AUDIT_EVENT_TYPES:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyAuditError(
                f"Invalid session policy audit event event_type {self.event_type!r}. Must be one of "
                f"{VALID_SESSION_POLICY_AUDIT_EVENT_TYPES!r}."
            )

        if self.timestamp is None or not isinstance(self.timestamp, datetime):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyAuditError(
                "Cannot build a session policy audit event with a non-datetime timestamp."
            )
