from dataclasses import (
    dataclass,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRollbackResult:
    """
    Immutable outcome produced after rolling a consumer projection
    execution capability registry event subscription lifecycle
    policy profile binding back to a previously recorded deployment.

    Attributes:
        previous_deployment: The deployment record that was current
            immediately before the rollback
        restored_deployment: The new deployment record created to
            reflect the restored state
        successful: Whether the rollback completed without error
    """

    previous_deployment: object

    restored_deployment: object

    successful: bool
