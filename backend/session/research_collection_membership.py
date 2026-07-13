from dataclasses import (
    dataclass,
)

from datetime import (
    datetime,
)


@dataclass
class ResearchCollectionMembership:
    """
    Represents membership of a research
    session in a research collection.
    """

    collection_id: str

    session_id: str

    added_at: datetime

    def to_dict(self):

        return {

            "collection_id":
                self.collection_id,

            "session_id":
                self.session_id,

            "added_at":
                self.added_at
                .isoformat(),
        }

    @classmethod
    def from_dict(

        cls,

        data,

    ):

        return cls(

            collection_id=(

                data[
                    "collection_id"
                ]
            ),

            session_id=(

                data[
                    "session_id"
                ]
            ),

            added_at=(

                datetime
                .fromisoformat(

                    data["added_at"]
                )
            ),
        )
