from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_decision_package import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionPackage,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergePlan:
    """
    Immutable, deterministic blueprint describing how an incoming
    consumer projection execution capability registry snapshot
    would be merged onto a base snapshot.

    Captures state only - it does not perform the merge, resolve
    conflicts, or persist data.

    Attributes:
        additions: Packages present only in the incoming snapshot,
            sorted by projection_name
        updates: Packages present in both snapshots whose decision
            package differs, taken from the incoming snapshot and
            sorted by projection_name
        unchanged: Packages present in both snapshots with an
            identical decision package, sorted by projection_name
    """

    additions: tuple[
        ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionPackage,
        ...,
    ]

    updates: tuple[
        ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionPackage,
        ...,
    ]

    unchanged: tuple[
        ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionPackage,
        ...,
    ]

    def to_dict(self):
        return {
            "additions": [
                package.to_dict()
                for package in self.additions
            ],
            "updates": [
                package.to_dict()
                for package in self.updates
            ],
            "unchanged": [
                package.to_dict()
                for package in self.unchanged
            ],
        }
