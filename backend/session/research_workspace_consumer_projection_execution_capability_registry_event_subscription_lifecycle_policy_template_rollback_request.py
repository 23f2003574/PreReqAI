from dataclasses import (
    dataclass,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRollbackRequest:
    """
    Immutable request to roll a deployed consumer projection
    execution capability registry event subscription lifecycle
    policy template back to a previously deployed version.

    The request is a value object only. It performs no lookup, no
    verification, and no rollback. Lookup, verification, and
    rollback are the responsibility of a rollback service.

    Attributes:
        deployment_id: The identifier of the deployment record that
            names the template to roll back
        target_version: The previously published version to restore
            as current
    """

    deployment_id: str

    target_version: str
