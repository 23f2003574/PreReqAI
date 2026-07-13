from dataclasses import (
    dataclass,
    field,
)

from .research_activity_event import (
    ResearchActivityEvent,
)


@dataclass
class ResearchActivityPage:
    """
    Represents one paginated activity
    timeline result.
    """

    items: list[
        ResearchActivityEvent
    ] = field(
        default_factory=list,
    )

    page: int = 1

    page_size: int = 50

    total: int = 0

    @property
    def has_next(self):

        return (

            self.page
            * self.page_size

            < self.total
        )

    @property
    def has_previous(self):

        return self.page > 1

    def to_dict(self):

        return {

            "items": [

                item.to_dict()

                for item

                in self.items
            ],

            "page":
                self.page,

            "page_size":
                self.page_size,

            "total":
                self.total,

            "has_next":
                self.has_next,

            "has_previous":
                self.has_previous,
        }
