from dataclasses import (
    dataclass,
)

from datetime import datetime


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRollbackResult:
    """
    Immutable outcome produced after rolling a deployed consumer
    projection execution capability registry event subscription
    lifecycle policy profile back to a previously deployed version.

    The result is a value object only. It performs no lookup, no
    verification, and no rollback. Lookup, verification, and
    rollback are the responsibility of a rollback service.

    Attributes:
        previous_version: The version that was active immediately
            before the rollback
        restored_version: The version that was restored as active
        rollback_id: The deterministic identifier of this rollback,
            derived from the profile, target environment, and
            restored version
        rolled_back_at: When the rollback occurred
        successful: Whether the rollback completed without error
    """

    previous_version: str

    restored_version: str

    rollback_id: str

    rolled_back_at: datetime

    successful: bool
