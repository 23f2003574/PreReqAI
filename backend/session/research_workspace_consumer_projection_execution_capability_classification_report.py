from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_classification import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityClassification,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityClassificationReport:
    """
    The immutable result of resolving a consumer projection's
    execution capability profile into a standardized domain
    classification, exposed to downstream consumers.

    Attributes:
        projection_name: Identifies the evaluated projection
        classification: The resolved capability classification
        profile: Profile reused from the capability profile
        executable: Flag reused from the capability profile
    """

    projection_name: str

    classification: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityClassification
    )

    profile: str

    executable: bool

    def to_dict(self):
        return {
            "projection_name": self.projection_name,
            "classification": self.classification.value,
            "profile": self.profile,
            "executable": self.executable,
        }
