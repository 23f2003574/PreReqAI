from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
)

from .research_activity_actor_type import (
    ResearchActivityActorType,
)

from .research_activity_type import (
    ResearchActivityType,
)


@dataclass
class ResearchActivityQuery:
    """
    Describes filtering and pagination
    for research activity history.
    """

    session_ids: set[
        str
    ] = field(
        default_factory=set,
    )

    activity_types: set[
        ResearchActivityType
    ] = field(
        default_factory=set,
    )

    actor_types: set[
        ResearchActivityActorType
    ] = field(
        default_factory=set,
    )

    occurred_from: (
        datetime | None
    ) = None

    occurred_to: (
        datetime | None
    ) = None

    page: int = 1

    page_size: int = 50

    newest_first: bool = True

    def __post_init__(self):

        if self.page < 1:

            raise ValueError(

                "Activity query page "
                "must be at least 1"
            )

        if self.page_size < 1:

            raise ValueError(

                "Activity query page size "
                "must be at least 1"
            )
