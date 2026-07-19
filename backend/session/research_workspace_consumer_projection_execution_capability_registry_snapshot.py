from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_decision_package import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionPackage,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistrySnapshot:
    """
    Immutable, consumer-facing read model of the complete state of
    a consumer projection execution capability registry.

    Captures state only - it does not write logs or persist data.

    Attributes:
        packages: Every registered decision package, sorted by
            projection_name
    """

    packages: tuple[
        ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionPackage,
        ...,
    ]

    def to_dict(self):
        return {
            "packages": [
                package.to_dict()
                for package in self.packages
            ],
        }
