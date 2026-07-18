from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability import (
    ResearchWorkspaceConsumerProjectionExecutionCapability,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityProfile:
    """
    A normalized capability classification for a consumer
    projection, exposed to downstream execution policy consumers.

    Attributes:
        projection_name: Projection name reused from the capability
            package
        capability: Capability reused from the capability package
        executable: Flag reused from the capability package
        profile: The resolved normalized profile classification
    """

    projection_name: str

    capability: (
        ResearchWorkspaceConsumerProjectionExecutionCapability
    )

    executable: bool

    profile: str

    def to_dict(self):
        return {
            "projection_name": self.projection_name,
            "capability": self.capability.value,
            "executable": self.executable,
            "profile": self.profile,
        }
