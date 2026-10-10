from dataclasses import (
    dataclass,
)

from datetime import datetime


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRollbackResult:
    """
    Immutable outcome produced after rolling a deployed consumer
    projection execution capability registry event subscription
    lifecycle policy template back to a previously deployed version.

    The result is a value object only. It performs no lookup, no
    verification, and no rollback. Lookup, verification, and
    rollback are the responsibility of a rollback service.

    Attributes:
        previous_version: The version that was current immediately
            before the rollback
        restored_version: The version that was restored as current
        rollback_successful: Whether the rollback completed without
            error
        rolled_back_at: When the rollback occurred
    """

    previous_version: str

    restored_version: str

    rollback_successful: bool

    rolled_back_at: datetime
