from dataclasses import (
    dataclass,
)

from datetime import datetime


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogVersion:
    """
    Immutable snapshot of a consumer projection execution capability
    registry event subscription lifecycle policy catalog's version
    at the moment it was read.

    The version is a value object only. It performs no catalog
    construction, no upgrade, and no history tracking. A catalog
    carries no upgrade history of its own, so previous_version
    reflects only what the caller producing this snapshot knew at
    the time; a version read directly from a catalog will always
    report a previous_version of None.

    Attributes:
        version: The catalog's version at the time of the snapshot
        created_at: When this version snapshot was taken
        previous_version: The catalog's version prior to this one,
            or None if no prior version is known
    """

    version: str

    created_at: datetime

    previous_version: (
        str | None
    )
