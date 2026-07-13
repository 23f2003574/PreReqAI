from dataclasses import (
    dataclass,
)

from datetime import (
    datetime,
)


@dataclass
class ResearchTag:
    """
    Represents a reusable normalized
    research workspace tag.
    """

    id: str

    name: str

    created_at: datetime

    def to_dict(self):

        return {

            "id":
                self.id,

            "name":
                self.name,

            "created_at":
                self.created_at
                .isoformat(),
        }

    @classmethod
    def from_dict(

        cls,

        data,

    ):

        return cls(

            id=data["id"],

            name=data["name"],

            created_at=(

                datetime
                .fromisoformat(

                    data["created_at"]
                )
            ),
        )
