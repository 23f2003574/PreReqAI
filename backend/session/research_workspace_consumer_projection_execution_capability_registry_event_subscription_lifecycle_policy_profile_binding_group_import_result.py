from dataclasses import (
    dataclass,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupImportResult:
    """
    Immutable outcome produced after importing consumer projection
    execution capability registry event subscription lifecycle
    policy profile binding groups from an export.

    Attributes:
        imported: An immutable tuple of group IDs that were newly
            registered or updated as a result of the import
        skipped: An immutable tuple of group IDs left untouched
            because they already matched the imported group
        failed: An immutable tuple of group IDs whose import could
            not be applied
    """

    imported: tuple

    skipped: tuple

    failed: tuple
