from dataclasses import (
    dataclass,
    field,
)

from .research_history_timeline_item import (
    ResearchHistoryTimelineItem,
)


@dataclass
class ResearchHistoryPage:
    """
    Represents one paginated result
    from the research history timeline.
    """

    items: list[
        ResearchHistoryTimelineItem
    ] = field(
        default_factory=list,
    )

    total: int = 0

    offset: int = 0

    limit: int = 50

    @property
    def returned(self):

        return len(
            self.items
        )

    @property
    def has_more(self):

        return (

            self.offset

            + self.returned

            < self.total
        )

    @property
    def next_offset(self):

        if not self.has_more:

            return None

        return (

            self.offset

            + self.returned
        )

    def to_dict(self):

        return {

            "items": [

                item.to_dict()

                for item

                in self.items
            ],

            "total":
                self.total,

            "offset":
                self.offset,

            "limit":
                self.limit,

            "returned":
                self.returned,

            "has_more":
                self.has_more,

            "next_offset":
                self.next_offset,
        }
