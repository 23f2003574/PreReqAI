from dataclasses import (
    dataclass,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupAuditHistory:
    """
    Immutable, chronologically ordered collection of audit records
    for a consumer projection execution capability registry event
    subscription lifecycle policy profile binding group.

    The history is a value object only. It performs no recording and
    has no effect on the group's operational state.

    Attributes:
        records: The audit records, in chronological order
    """

    records: tuple
