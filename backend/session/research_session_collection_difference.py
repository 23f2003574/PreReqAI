from dataclasses import (
    dataclass,
    field,
)


@dataclass
class ResearchSessionCollectionDifference:
    """
    Represents shared and exclusive
    identifiers across two session-owned
    collections.
    """

    shared_ids: list[
        str
    ] = field(
        default_factory=list,
    )

    first_only_ids: list[
        str
    ] = field(
        default_factory=list,
    )

    second_only_ids: list[
        str
    ] = field(
        default_factory=list,
    )

    @property
    def shared_count(self):

        return len(
            self.shared_ids
        )

    @property
    def first_only_count(self):

        return len(
            self.first_only_ids
        )

    @property
    def second_only_count(self):

        return len(
            self.second_only_ids
        )

    @property
    def differs(self):

        return bool(

            self.first_only_ids

            or

            self.second_only_ids
        )

    def to_dict(self):

        return {

            "shared_ids":
                list(
                    self.shared_ids
                ),

            "first_only_ids":
                list(
                    self.first_only_ids
                ),

            "second_only_ids":
                list(
                    self.second_only_ids
                ),

            "shared_count":
                self.shared_count,

            "first_only_count":
                self.first_only_count,

            "second_only_count":
                self.second_only_count,

            "differs":
                self.differs,
        }
