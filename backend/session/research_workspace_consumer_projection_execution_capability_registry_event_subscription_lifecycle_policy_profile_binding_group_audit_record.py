from dataclasses import (
    dataclass,
)

from datetime import datetime

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_group_audit_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupAuditError,
)

_VALID_OPERATIONS = (
    "create",
    "update",
    "remove",
    "publish",
    "deploy",
    "rollback",
    "release",
    "retire",
    "sync",
    "export",
    "import",
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupAuditRecord:
    """
    Immutable record of a single consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding group lifecycle operation, kept for traceability,
    debugging, and compliance.

    The record is a value object only. It performs no recording and
    has no effect on the group's operational state.

    Attributes:
        audit_id: The record's unique identifier
        group_id: The identifier of the group the operation concerned
        operation: The kind of lifecycle operation this record
            captures (one of "create", "update", "remove", "publish",
            "deploy", "rollback", "release", "retire", "sync",
            "export", or "import")
        timestamp: When the operation occurred
        actor: The identifier of the user, service, or system that
            performed the operation
    """

    audit_id: str

    group_id: str

    operation: str

    timestamp: datetime

    actor: str

    def __post_init__(self):
        if self.audit_id is None or not self.audit_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupAuditError(
                "Cannot build an audit record with an empty or blank audit ID."
            )

        if self.group_id is None or not self.group_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupAuditError(
                "Cannot build an audit record with an empty or blank group ID."
            )

        if self.operation is None or not self.operation.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupAuditError(
                "Cannot build an audit record with an empty or blank operation."
            )

        if self.operation not in _VALID_OPERATIONS:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupAuditError(
                f"Invalid audit record operation {self.operation!r}. Must be one of {_VALID_OPERATIONS!r}."
            )

        if self.timestamp is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupAuditError(
                "Cannot build an audit record with a None timestamp."
            )

        if self.actor is None or not self.actor.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupAuditError(
                "Cannot build an audit record with an empty or blank actor."
            )
