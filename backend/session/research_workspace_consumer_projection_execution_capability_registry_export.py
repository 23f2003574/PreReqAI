from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_decision_package import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionPackage,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryExport:
    """
    Immutable, portable representation of the complete state of a
    consumer projection execution capability registry, suitable for
    downstream integrations.

    Captures state only - it does not write logs or persist data.

    Attributes:
        packages: Every registered decision package, sorted by
            projection_name
        total_projections: The number of registered packages
    """

    packages: tuple[
        ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionPackage,
        ...,
    ]

    total_projections: int

    def to_dict(self):
        return {
            "packages": [
                package.to_dict()
                for package in self.packages
            ],
            "total_projections": self.total_projections,
        }
