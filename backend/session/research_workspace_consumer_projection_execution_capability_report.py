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
class ResearchWorkspaceConsumerProjectionExecutionCapabilityReport:
    """
    The immutable result of resolving a consumer projection's
    execution outcome into a normalized execution capability,
    exposed to downstream execution policy.

    Attributes:
        projection_name: Identifies the evaluated projection
        capability: The resolved execution capability
        reason: The primary cause of the capability
        executable: Whether the projection is intrinsically
            executable right now
    """

    projection_name: str

    capability: (
        ResearchWorkspaceConsumerProjectionExecutionCapability
    )

    reason: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityReason
    )

    executable: bool

    def to_dict(self):
        return {
            "projection_name": self.projection_name,
            "capability": self.capability.value,
            "reason": self.reason.value,
            "executable": self.executable,
        }
