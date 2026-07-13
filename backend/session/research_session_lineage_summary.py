from dataclasses import (
    dataclass,
)


@dataclass
class ResearchSessionLineageSummary:
    """
    Provides compact lineage information
    for one research session.
    """

    session_id: str

    root_session_id: str

    parent_session_id: (
        str | None
    )

    depth: int

    ancestor_count: int

    child_count: int

    descendant_count: int

    def to_dict(self):

        return {

            "session_id":
                self.session_id,

            "root_session_id":
                self.root_session_id,

            "parent_session_id":
                self.parent_session_id,

            "depth":
                self.depth,

            "ancestor_count":
                self.ancestor_count,

            "child_count":
                self.child_count,

            "descendant_count":
                self.descendant_count,
        }
