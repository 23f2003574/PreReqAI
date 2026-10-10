from dataclasses import (
    dataclass,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentImportResult:
    """
    Immutable outcome produced after importing consumer projection
    execution capability registry event subscription lifecycle
    policy profile assignments from an export.

    Attributes:
        imported: An immutable tuple of target IDs that were newly
            assigned as a result of the import
        skipped: An immutable tuple of target IDs left untouched
            because they already carried the imported assignment
        failed: An immutable tuple of target IDs whose assignment
            could not be applied
    """

    imported: tuple

    skipped: tuple

    failed: tuple
