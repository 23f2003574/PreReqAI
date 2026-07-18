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
class ResearchWorkspaceConsumerProjectionExecutionCapabilitySummary:
    """
    A compact, presentation-ready summary of a consumer projection's
    execution capability, for fast consumer inspection.

    Attributes:
        projection_name: Identifies the evaluated projection
        capability: Capability reused from the execution capability
            report
        reason: Reason reused from the execution capability report
        title: Short human-readable label for the capability
        description: Human-readable explanation of the capability
        executable: Flag reused from the execution capability report
    """

    projection_name: str

    capability: (
        ResearchWorkspaceConsumerProjectionExecutionCapability
    )

    reason: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityReason
    )

    title: str

    description: str

    executable: bool

    def to_dict(self):
        return {
            "projection_name": self.projection_name,
            "capability": self.capability.value,
            "reason": self.reason.value,
            "title": self.title,
            "description": self.description,
            "executable": self.executable,
        }
