from dataclasses import (
    dataclass,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogStatistics:
    """
    Immutable summary statistics describing a consumer projection
    execution capability registry event subscription lifecycle
    policy catalog.

    The statistics are a value object only. They perform no
    computation, no catalog lookup, and no reporting.

    Attributes:
        total_policies: The number of policies in the catalog
        unique_policy_identifiers: The number of distinct policy
            identifiers in the catalog
        first_policy_identifier: The first policy identifier in
            catalog order, or None if the catalog is empty
        last_policy_identifier: The last policy identifier in
            catalog order, or None if the catalog is empty
        empty_catalog: Whether the catalog contains no policies
    """

    total_policies: int

    unique_policy_identifiers: int

    first_policy_identifier: (
        str | None
    )

    last_policy_identifier: (
        str | None
    )

    empty_catalog: bool
