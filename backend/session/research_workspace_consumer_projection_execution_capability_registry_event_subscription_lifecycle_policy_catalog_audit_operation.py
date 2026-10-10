from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogAuditOperation(
    str,
    Enum,
):
    """
    Kinds of catalog-level operation that can be recorded in a
    consumer projection execution capability registry event
    subscription lifecycle policy catalog's audit trail.

    This enum only names the possible operations. It performs no
    recording, no catalog construction, and no evaluation.
    """

    CREATED = (
        "created"
    )

    IMPORTED = (
        "imported"
    )

    SYNCHRONIZED = (
        "synchronized"
    )

    VERSION_UPDATED = (
        "version_updated"
    )

    POLICY_ADDED = (
        "policy_added"
    )

    POLICY_UPDATED = (
        "policy_updated"
    )

    POLICY_REMOVED = (
        "policy_removed"
    )
