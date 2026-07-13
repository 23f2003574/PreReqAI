from dataclasses import (
    dataclass,
)

from datetime import datetime

from .research_session_kind import (
    ResearchSessionKind,
)

from .research_session_status import (
    ResearchSessionStatus,
)


@dataclass
class ResearchSessionListItem:
    """
    Represents one frontend-ready
    research session discovery result.
    """

    session_id: str

    display_name: str

    description: str | None

    paper_id: str | None

    paper_title: str | None

    status: (
        ResearchSessionStatus
    )

    archived: bool

    kind: (
        ResearchSessionKind
    )

    parent_session_id: (
        str | None
    )

    root_session_id: str

    depth: int

    child_count: int

    descendant_count: int

    created_at: datetime

    updated_at: datetime

    def to_dict(self):

        return {

            "session_id":
                self.session_id,

            "display_name":
                self.display_name,

            "description":
                self.description,

            "paper_id":
                self.paper_id,

            "paper_title":
                self.paper_title,

            "status":
                self.status.value,

            "archived":
                self.archived,

            "kind":
                self.kind.value,

            "parent_session_id":
                self.parent_session_id,

            "root_session_id":
                self.root_session_id,

            "depth":
                self.depth,

            "child_count":
                self.child_count,

            "descendant_count":
                self.descendant_count,

            "created_at":
                self.created_at
                .isoformat(),

            "updated_at":
                self.updated_at
                .isoformat(),
        }
