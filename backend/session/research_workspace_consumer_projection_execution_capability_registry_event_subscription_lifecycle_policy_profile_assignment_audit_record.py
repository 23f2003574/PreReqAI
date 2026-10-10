from dataclasses import (
    dataclass,
)

from datetime import datetime

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_assignment_audit_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentAuditError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentAuditRecord:
    """
    Immutable record of a single consumer projection execution
    capability registry event subscription lifecycle policy profile
    assignment change, kept for traceability, debugging, and
    compliance.

    The record is a value object only. It performs no recording and
    has no effect on the active assignment state.

    Attributes:
        audit_id: The record's unique identifier
        target_id: The identifier of the target the change concerned
        profile_id: The identifier of the profile involved, or None
            for an "unassign" operation
        operation: The kind of change this record captures
            ("assign" or "unassign")
        timestamp: When the change occurred
    """

    audit_id: str

    target_id: str

    profile_id: str | None

    operation: str

    timestamp: datetime

    def __post_init__(self):
        if self.audit_id is None or not self.audit_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentAuditError(
                "Cannot build an audit record with an empty or blank audit ID."
            )

        if self.target_id is None or not self.target_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentAuditError(
                "Cannot build an audit record with an empty or blank target ID."
            )

        if self.operation is None or not self.operation.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentAuditError(
                "Cannot build an audit record with an empty or blank operation."
            )

        if self.operation not in ("assign", "unassign"):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentAuditError(
                f"Invalid audit record operation {self.operation!r}. Must be 'assign' or 'unassign'."
            )

        if self.operation == "assign" and (self.profile_id is None or not self.profile_id.strip()):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentAuditError(
                "Profile ID cannot be empty or blank for an 'assign' operation."
            )

        if self.timestamp is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentAuditError(
                "Cannot build an audit record with a None timestamp."
            )
