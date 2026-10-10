from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_assignment_rollback_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRollbackError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRollbackRequest:
    """
    Immutable request to restore a consumer projection execution
    capability registry event subscription lifecycle policy profile
    assignment target to the state recorded by a specific audit
    record.

    The request is a value object only. It performs no lookup, no
    verification, and no rollback. Lookup, verification, and
    rollback are the responsibility of a rollback service.

    Attributes:
        target_id: The identifier of the target to roll back
        audit_id: The identifier of the audit record whose state
            should be restored
    """

    target_id: str

    audit_id: str

    def __post_init__(self):
        if self.target_id is None or not self.target_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRollbackError(
                "Cannot build a rollback request with an empty or blank target ID."
            )

        if self.audit_id is None or not self.audit_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRollbackError(
                "Cannot build a rollback request with an empty or blank audit ID."
            )
