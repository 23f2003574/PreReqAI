from dataclasses import (
    dataclass,
)


@dataclass
class ResearchSessionDivergence:
    """
    Describes where two related research
    sessions meet in lineage and how their
    branch paths separate.
    """

    common_ancestor_session_id: (
        str | None
    )

    first_path_from_common_ancestor: (
        list[str]
    )

    second_path_from_common_ancestor: (
        list[str]
    )

    first_divergent_session_id: (
        str | None
    )

    second_divergent_session_id: (
        str | None
    )

    first_branch_checkpoint_id: (
        str | None
    )

    first_branch_version_id: (
        str | None
    )

    second_branch_checkpoint_id: (
        str | None
    )

    second_branch_version_id: (
        str | None
    )

    def to_dict(self):

        return {

            "common_ancestor_session_id":
                self.common_ancestor_session_id,

            "first_path_from_common_ancestor":
                list(
                    self
                    .first_path_from_common_ancestor
                ),

            "second_path_from_common_ancestor":
                list(
                    self
                    .second_path_from_common_ancestor
                ),

            "first_divergent_session_id":
                self
                .first_divergent_session_id,

            "second_divergent_session_id":
                self
                .second_divergent_session_id,

            "first_branch_checkpoint_id":
                self
                .first_branch_checkpoint_id,

            "first_branch_version_id":
                self
                .first_branch_version_id,

            "second_branch_checkpoint_id":
                self
                .second_branch_checkpoint_id,

            "second_branch_version_id":
                self
                .second_branch_version_id,
        }
