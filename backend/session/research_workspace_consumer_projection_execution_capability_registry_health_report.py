from dataclasses import (
    dataclass,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryHealthReport:
    """
    Immutable, consumer-facing aggregate of a consumer projection
    execution capability registry's health, derived directly from
    registered decision packages.

    Captures state only - it does not write logs or persist data.

    Attributes:
        total_projections: The number of registered packages
        executable_projections: Packages with executable == True
        non_executable_projections: Packages with executable ==
            False
        accepted_projections: Packages with decision == ACCEPT
        review_projections: Packages with decision == REVIEW
        rejected_projections: Packages with decision == REJECT
    """

    total_projections: int

    executable_projections: int

    non_executable_projections: int

    accepted_projections: int

    review_projections: int

    rejected_projections: int

    def to_dict(self):
        return {
            "total_projections": self.total_projections,
            "executable_projections": self.executable_projections,
            "non_executable_projections": self.non_executable_projections,
            "accepted_projections": self.accepted_projections,
            "review_projections": self.review_projections,
            "rejected_projections": self.rejected_projections,
        }
