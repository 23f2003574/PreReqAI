from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_classification import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityClassification,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityDescriptor:
    """
    A compact, presentation-ready descriptor of a consumer
    projection's execution capability classification, for fast
    consumer inspection.

    Attributes:
        projection_name: Identifies the evaluated projection
        classification: Classification reused from the
            classification report
        title: Short human-readable label for the classification
        description: Human-readable explanation of the
            classification
        executable: Flag reused from the classification report
    """

    projection_name: str

    classification: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityClassification
    )

    title: str

    description: str

    executable: bool

    def to_dict(self):
        return {
            "projection_name": self.projection_name,
            "classification": self.classification.value,
            "title": self.title,
            "description": self.description,
            "executable": self.executable,
        }
