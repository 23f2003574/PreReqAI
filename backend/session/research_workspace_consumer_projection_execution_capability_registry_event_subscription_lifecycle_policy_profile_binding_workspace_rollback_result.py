from dataclasses import (
    dataclass,
)

from typing import Mapping


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRollbackResult:
    """
    Immutable outcome produced after rolling a consumer projection
    execution capability registry event subscription lifecycle
    policy profile binding workspace back to a previously recorded
    deployment.

    Attributes:
        previous_deployment: The deployment record that was current
            immediately before the rollback
        restored_deployment: The new deployment record created to
            reflect the restored state
        restored_resources: An immutable mapping of resource kind
            ("bindings", "templates", "presets", "groups") to the
            identifiers of that kind of resource restored as part of
            the rollback
        successful: Whether the rollback completed without error
    """

    previous_deployment: object

    restored_deployment: object

    restored_resources: Mapping[str, tuple]

    successful: bool
