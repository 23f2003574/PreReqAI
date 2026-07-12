from dataclasses import (
    dataclass,
)

from .research_session_comparison import (
    ResearchSessionComparison,
)


@dataclass
class ResearchRecoveryPreview:
    """
    Describes the expected effect of
    restoring a historical checkpoint.
    """

    session_id: str

    checkpoint_id: str

    snapshot_version_id: str

    comparison: (
        ResearchSessionComparison
    )

    @property
    def has_changes(self) -> bool:

        return (
            self.comparison
            .has_changes
        )

    @property
    def change_count(self) -> int:

        return (
            self.comparison
            .change_count
        )

    def to_dict(self):

        return {

            "session_id":
                self.session_id,

            "checkpoint_id":
                self.checkpoint_id,

            "snapshot_version_id":
                self.snapshot_version_id,

            "has_changes":
                self.has_changes,

            "change_count":
                self.change_count,

            "comparison":
                self.comparison
                .to_dict(),
        }
