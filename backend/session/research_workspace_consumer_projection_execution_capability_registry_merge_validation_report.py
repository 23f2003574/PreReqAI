from dataclasses import (
    dataclass,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergeValidationReport:
    """
    Immutable, consumer-facing summary of a consumer projection
    execution capability registry merge plan integrity check.

    Captures state only - it does not write logs or persist data.

    Attributes:
        additions: The number of addition entries inspected
        updates: The number of update entries inspected
        unchanged: The number of unchanged entries inspected
        duplicate_projection_names: Projection names that are
            unsafe to apply - either because they appear more than
            once across the merge plan's collections, or because
            the projection name itself is empty
        is_valid: True when duplicate_projection_names is empty
    """

    additions: int

    updates: int

    unchanged: int

    duplicate_projection_names: tuple[
        str,
        ...,
    ]

    is_valid: bool

    def to_dict(self):
        return {
            "additions": self.additions,
            "updates": self.updates,
            "unchanged": self.unchanged,
            "duplicate_projection_names": list(
                self.duplicate_projection_names
            ),
            "is_valid": self.is_valid,
        }
