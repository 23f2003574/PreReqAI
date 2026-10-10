from dataclasses import (
    dataclass,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRollbackResult:
    """
    Immutable outcome produced after rolling a consumer projection
    execution capability registry event subscription lifecycle
    policy profile binding group back to a previously recorded
    deployment.

    Attributes:
        previous_deployment: The deployment record that was current
            immediately before the rollback
        restored_deployment: The new deployment record created to
            reflect the restored state
        restored_bindings: An immutable, order-preserving tuple of the
            identifiers of every member binding restored together as
            part of the rollback
        successful: Whether the rollback completed without error
    """

    previous_deployment: object

    restored_deployment: object

    restored_bindings: tuple

    successful: bool
