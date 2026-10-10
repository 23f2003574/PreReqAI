from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_transaction_entry import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionEntry,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransaction:
    """
    An immutable, ordered set of changes to apply atomically to a
    consumer projection execution capability registry.

    Attributes:
        entries: The transaction entries, applied in order
    """

    entries: tuple[
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionEntry,
        ...,
    ]
