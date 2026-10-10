from dataclasses import (
    dataclass,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistory:
    """
    Immutable, chronological collection of consumer projection
    execution capability registry event subscription lifecycle
    policy evaluation history entries.

    The history owns only ordered storage. It performs no replay,
    navigation, search, filtering, persistence, sequence number
    generation, policy evaluation, or logging.

    Attributes:
        entries: The history entries, in chronological order
        entry_count: The number of entries in the history
    """

    entries: tuple

    entry_count: int
