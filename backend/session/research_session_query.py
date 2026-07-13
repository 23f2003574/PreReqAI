from dataclasses import (
    dataclass,
    field,
)

from .research_session_kind import (
    ResearchSessionKind,
)

from .research_session_sort_order import (
    ResearchSessionSortOrder,
)

from .research_session_status import (
    ResearchSessionStatus,
)


@dataclass
class ResearchSessionQuery:
    """
    Describes filtering, searching,
    lineage scoping, sorting, and
    pagination for research sessions.
    """

    search: str | None = None

    statuses: set[
        ResearchSessionStatus
    ] = field(
        default_factory=set,
    )

    archived: bool | None = None

    kinds: set[
        ResearchSessionKind
    ] = field(
        default_factory=set,
    )

    lineage_root_session_id: (
        str | None
    ) = None

    direct_parent_session_id: (
        str | None
    ) = None

    sort_order: (
        ResearchSessionSortOrder
    ) = (
        ResearchSessionSortOrder
        .UPDATED_NEWEST
    )

    offset: int = 0

    limit: int = 50

    def __post_init__(self):

        if self.offset < 0:

            raise ValueError(

                "Research session query "
                "offset cannot be negative"
            )

        if self.limit <= 0:

            raise ValueError(

                "Research session query "
                "limit must be greater "
                "than zero"
            )

        self.statuses = {

            (

                status

                if isinstance(

                    status,

                    ResearchSessionStatus,
                )

                else (

                    ResearchSessionStatus(
                        status
                    )
                )
            )

            for status

            in self.statuses
        }

        self.kinds = {

            (

                kind

                if isinstance(

                    kind,

                    ResearchSessionKind,
                )

                else (

                    ResearchSessionKind(
                        kind
                    )
                )
            )

            for kind

            in self.kinds
        }

        if not isinstance(

            self.sort_order,

            ResearchSessionSortOrder,
        ):

            self.sort_order = (

                ResearchSessionSortOrder(

                    self.sort_order
                )
            )

        if self.search is not None:

            self.search = (

                self.search.strip()

                or None
            )
