from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_decision_package import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionPackage,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryDiff:
    """
    Immutable, consumer-facing change set between two consumer
    projection execution capability registry snapshots.

    Captures state only - it does not write logs or persist data.

    Attributes:
        added: Packages present only in the current snapshot,
            sorted by projection_name
        removed: Packages present only in the previous snapshot,
            sorted by projection_name
        modified: Packages present in both snapshots whose decision
            package differs, taken from the current snapshot and
            sorted by projection_name
    """

    added: tuple[
        ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionPackage,
        ...,
    ]

    removed: tuple[
        ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionPackage,
        ...,
    ]

    modified: tuple[
        ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionPackage,
        ...,
    ]

    def to_dict(self):
        return {
            "added": [
                package.to_dict()
                for package in self.added
            ],
            "removed": [
                package.to_dict()
                for package in self.removed
            ],
            "modified": [
                package.to_dict()
                for package in self.modified
            ],
        }
