from dataclasses import (
    dataclass,
    field,
)

from datetime import datetime

from .research_checkpoint_reason import (
    ResearchCheckpointReason,
)

from .research_history_sort_order import (
    ResearchHistorySortOrder,
)


@dataclass
class ResearchHistoryQuery:
    """
    Describes filtering, sorting,
    searching, and pagination options
    for a research checkpoint timeline.
    """

    reasons: set[
        ResearchCheckpointReason
    ] = field(
        default_factory=set,
    )

    pinned: bool | None = None

    recovery_only: bool = False

    search: str | None = None

    created_from: datetime | None = None

    created_until: datetime | None = None

    sort_order: (
        ResearchHistorySortOrder
    ) = (
        ResearchHistorySortOrder
        .NEWEST
    )

    offset: int = 0

    limit: int = 50

    def __post_init__(self):

        if self.offset < 0:

            raise ValueError(

                "Research history offset "
                "cannot be negative"
            )

        if self.limit <= 0:

            raise ValueError(

                "Research history limit "
                "must be greater than zero"
            )

        if (

            self.created_from is not None

            and

            self.created_until is not None

            and

            self.created_from

            > self.created_until
        ):

            raise ValueError(

                "Research history start date "
                "cannot be after end date"
            )

        self.reasons = {

            (

                reason

                if isinstance(

                    reason,

                    ResearchCheckpointReason,
                )

                else (

                    ResearchCheckpointReason(
                        reason
                    )
                )
            )

            for reason

            in self.reasons
        }

        if not isinstance(

            self.sort_order,

            ResearchHistorySortOrder,
        ):

            self.sort_order = (

                ResearchHistorySortOrder(

                    self.sort_order
                )
            )
