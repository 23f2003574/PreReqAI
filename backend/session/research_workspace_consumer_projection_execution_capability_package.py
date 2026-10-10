from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability import (
    ResearchWorkspaceConsumerProjectionExecutionCapability,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityPackage:
    """
    Portable, immutable consumer-facing package representing the
    resolved execution capability for one projection.

    Captures state only - it does not write logs or persist data.

    Attributes:
        projection_name: Projection name reused from the snapshot
        capability: Capability reused from the snapshot
        executable: Flag reused from the snapshot
        title: Title reused from the snapshot
        description: Description reused from the snapshot
    """

    projection_name: str

    capability: (
        ResearchWorkspaceConsumerProjectionExecutionCapability
    )

    executable: bool

    title: str

    description: str

    def to_dict(self):
        return {
            "projection_name": self.projection_name,
            "capability": self.capability.value,
            "executable": self.executable,
            "title": self.title,
            "description": self.description,
        }
