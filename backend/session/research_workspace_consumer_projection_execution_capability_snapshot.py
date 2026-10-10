from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability import (
    ResearchWorkspaceConsumerProjectionExecutionCapability,
)

from .research_workspace_consumer_projection_execution_capability_reason import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityReason,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilitySnapshot:
    """
    Compact, immutable, consumer-facing read model of a consumer
    projection's execution capability.

    Attributes:
        projection_name: Projection name reused from the input artifacts
        capability: Capability reused from the capability report
        reason: Reason reused from the capability report
        executable: Flag reused from the capability report
        title: Title reused from the capability summary
        description: Description reused from the capability summary
    """

    projection_name: str

    capability: (
        ResearchWorkspaceConsumerProjectionExecutionCapability
    )

    reason: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityReason
    )

    executable: bool

    title: str

    description: str

    def to_dict(self):
        return {
            "projection_name": self.projection_name,
            "capability": self.capability.value,
            "reason": self.reason.value,
            "executable": self.executable,
            "title": self.title,
            "description": self.description,
        }
