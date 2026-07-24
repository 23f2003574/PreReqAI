from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_catalog_audit_entry import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogAuditEntry,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogAuditTrail:
    """
    Immutable, ordered record of every operation performed against a
    consumer projection execution capability registry event
    subscription lifecycle policy catalog.

    The audit trail is a value object only. It performs no
    recording, no catalog construction, and no evaluation.

    Attributes:
        entries: The audit entries, in insertion order
        total_entries: The number of entries in the audit trail
    """

    entries: tuple[
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogAuditEntry,
        ...,
    ]

    total_entries: int
