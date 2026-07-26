from dataclasses import (
    dataclass,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRollbackRequest:
    """
    Immutable request to roll a deployed consumer projection
    execution capability registry event subscription lifecycle
    policy profile back to a previously deployed version within a
    target environment.

    The request is a value object only. It performs no lookup, no
    verification, and no rollback. Lookup, verification, and
    rollback are the responsibility of a rollback service.

    Attributes:
        profile_id: The identifier of the profile to roll back
        target_environment: The runtime environment to roll back
        target_version: The previously deployed version to restore
            as active
        reason: A human-readable justification for the rollback,
            kept as part of the audit trail
    """

    profile_id: str

    target_environment: str

    target_version: str

    reason: str
