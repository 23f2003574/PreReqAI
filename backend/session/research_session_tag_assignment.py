from dataclasses import (
    dataclass,
)

from datetime import (
    datetime,
)


@dataclass
class ResearchSessionTagAssignment:
    """
    Represents the assignment of one
    research tag to one research session.
    """

    session_id: str

    tag_id: str

    assigned_at: datetime

    def to_dict(self):

        return {

            "session_id":
                self.session_id,

            "tag_id":
                self.tag_id,

            "assigned_at":
                self.assigned_at
                .isoformat(),
        }

    @classmethod
    def from_dict(

        cls,

        data,

    ):

        return cls(

            session_id=(
                data["session_id"]
            ),

            tag_id=(
                data["tag_id"]
            ),

            assigned_at=(

                datetime
                .fromisoformat(

                    data["assigned_at"]
                )
            ),
        )
