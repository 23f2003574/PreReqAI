from dataclasses import (
    dataclass,
    field,
)

from .research_snapshot_validation_issue import (
    ResearchSnapshotValidationIssue,
)


@dataclass
class ResearchSnapshotValidationResult:
    """
    Represents the result of snapshot
    structural and referential validation.
    """

    issues: list[
        ResearchSnapshotValidationIssue
    ] = field(
        default_factory=list,
    )

    @property
    def is_valid(self):

        return len(
            self.issues
        ) == 0

    def to_dict(self):

        return {

            "is_valid":
                self.is_valid,

            "issues": [

                issue.to_dict()

                for issue

                in self.issues
            ],
        }
