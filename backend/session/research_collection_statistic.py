from dataclasses import (
    dataclass,
)


@dataclass
class ResearchCollectionStatistic:
    """
    Membership statistics for one
    research collection.
    """

    collection_id: str

    collection_name: str

    session_count: int

    def to_dict(self):

        return {

            "collection_id":
                self.collection_id,

            "collection_name":
                self.collection_name,

            "session_count":
                self.session_count,
        }
