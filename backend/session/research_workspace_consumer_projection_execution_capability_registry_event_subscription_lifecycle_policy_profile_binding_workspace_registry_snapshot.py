from dataclasses import (
    dataclass,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRegistrySnapshot:
    """
    Immutable snapshot of a consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    workspace registry's state at the moment it was taken.

    The snapshot is a value object only. It performs no registration,
    no lookup, and no generation. Generation is the responsibility of
    a binding workspace registry service.

    Attributes:
        workspace_count: The number of registered workspaces at the
            moment of the snapshot
        snapshot_count: The number of times the registry has had its
            state snapshotted, including the snapshot this count is
            carried on
    """

    workspace_count: int

    snapshot_count: int
