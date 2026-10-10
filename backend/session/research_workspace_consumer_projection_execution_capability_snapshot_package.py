from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability import (
    ResearchWorkspaceConsumerProjectionExecutionCapability,
)

from .research_workspace_consumer_projection_execution_capability_classification import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityClassification,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilitySnapshotPackage:
    """
    Compact, immutable, consumer-facing package assembling the
    complete execution capability state for one projection.

    Attributes:
        projection_name: Projection name reused from the input artifacts
        capability: Capability reused from the capability snapshot
        classification: Classification reused from the capability
            descriptor
        executable: Flag reused from the input artifacts
        title: Title reused from the capability descriptor
        description: Description reused from the capability
            descriptor
    """

    projection_name: str

    capability: (
        ResearchWorkspaceConsumerProjectionExecutionCapability
    )

    classification: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityClassification
    )

    executable: bool

    title: str

    description: str

    def to_dict(self):
        return {
            "projection_name": self.projection_name,
            "capability": self.capability.value,
            "classification": self.classification.value,
            "executable": self.executable,
            "title": self.title,
            "description": self.description,
        }
