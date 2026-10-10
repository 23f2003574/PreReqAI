from dataclasses import (
    dataclass,
)

from datetime import (
    datetime,
)

from typing import Mapping


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSnapshot:
    """
    Immutable snapshot of a consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    workspace's state at the moment it was taken.

    The snapshot is a value object only. It performs no creation and
    no generation. Generation is the responsibility of a binding
    workspace service.

    Attributes:
        workspace_id: The identifier of the workspace the snapshot
            was taken of
        created_at: The instant the snapshot was taken
        resource_counts: An immutable mapping of resource kind
            ("bindings", "templates", "presets", "groups") to the
            number of that kind of resource in the workspace at the
            moment of the snapshot
    """

    workspace_id: str

    created_at: datetime

    resource_counts: Mapping[str, int]
