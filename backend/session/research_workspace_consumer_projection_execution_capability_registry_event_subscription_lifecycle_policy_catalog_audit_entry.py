from dataclasses import (
    dataclass,
)

from datetime import datetime

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_catalog_audit_operation import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogAuditOperation,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogAuditEntry:
    """
    Immutable record of a single catalog-level operation performed
    against a consumer projection execution capability registry
    event subscription lifecycle policy catalog.

    The entry is a value object only. It performs no recording, no
    catalog construction, and no evaluation.

    Attributes:
        sequence_number: This entry's position in the audit trail
        operation: The kind of operation this entry records
        policy_identifier: The identifier of the policy the
            operation concerned, or None for a catalog-level
            operation not tied to a single policy
        timestamp: When the operation occurred
    """

    sequence_number: int

    operation: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogAuditOperation
    )

    policy_identifier: (
        str | None
    )

    timestamp: datetime
