from dataclasses import (
    dataclass,
)


@dataclass
class ResearchLineageStatistics:
    """
    Aggregate statistics describing
    research branching structure.
    """

    total_roots: int

    total_branches: int

    maximum_depth: int

    average_depth: float

    deepest_session_id: (
        str | None
    )

    most_branched_session_id: (
        str | None
    )

    most_branched_direct_children: int

    def to_dict(self):

        return {

            "total_roots":
                self.total_roots,

            "total_branches":
                self.total_branches,

            "maximum_depth":
                self.maximum_depth,

            "average_depth":
                self.average_depth,

            "deepest_session_id":
                self.deepest_session_id,

            "most_branched_session_id":
                self.most_branched_session_id,

            "most_branched_direct_children":
                self.most_branched_direct_children,
        }
