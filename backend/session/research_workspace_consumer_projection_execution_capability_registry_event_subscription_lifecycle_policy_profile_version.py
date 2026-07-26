from dataclasses import (
    dataclass,
)

from datetime import datetime


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersion:
    """
    Immutable snapshot of a consumer projection execution capability
    registry event subscription lifecycle policy profile's grouped
    policy identifiers at a single published version.

    The version is a value object only. It performs no publication,
    no history tracking, and no rollback. Publication and history
    tracking are the responsibility of a profile version service.

    Attributes:
        version: The published version identifier
        policy_identifiers: An immutable, order-preserving tuple of
            the lifecycle policy identifiers grouped under this
            version
        created_at: When this version was published
    """

    version: str

    policy_identifiers: tuple[
        str,
        ...,
    ]

    created_at: datetime
