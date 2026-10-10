from dataclasses import (
    dataclass,
)

from datetime import (
    datetime,
)


@dataclass
class ResearchCollection:
    """
    Represents a user-curated collection
    of research sessions.
    """

    id: str

    name: str

    description: str | None

    created_at: datetime

    updated_at: datetime

    def to_dict(self):

        return {

            "id":
                self.id,

            "name":
                self.name,

            "description":
                self.description,

            "created_at":
                self.created_at
                .isoformat(),

            "updated_at":
                self.updated_at
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

            description=(
                data.get(
                    "description"
                )
            ),

            created_at=(

                datetime
                .fromisoformat(

                    data["created_at"]
                )
            ),

            updated_at=(

                datetime
                .fromisoformat(

                    data["updated_at"]
                )
            ),
        )
