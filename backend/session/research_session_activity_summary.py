from dataclasses import (
    dataclass,
)

from datetime import (
    datetime,
)


@dataclass
class ResearchSessionActivitySummary:
    """
    Summarizes recent activity for one
    research session.
    """

    session_id: str

    display_name: str

    lifecycle_status: str

    archived: bool

    last_activity_at: (
        datetime | None
    )

    activity_count: int

    def to_dict(self):

        return {

            "session_id":
                self.session_id,

            "display_name":
                self.display_name,

            "lifecycle_status":
                self.lifecycle_status,

            "archived":
                self.archived,

            "last_activity_at": (

                self.last_activity_at
                .isoformat()

                if (

                    self.last_activity_at
                    is not None
                )

                else None
            ),

            "activity_count":
                self.activity_count,
        }
