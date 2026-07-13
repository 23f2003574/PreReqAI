from datetime import timezone

from .research_session_kind import (
    ResearchSessionKind,
)

from .research_session_list_item import (
    ResearchSessionListItem,
)

from .research_session_page import (
    ResearchSessionPage,
)

from .research_session_sort_order import (
    ResearchSessionSortOrder,
)

from .research_session_status import (
    ResearchSessionStatus,
)


class ResearchSessionQueryService:
    """
    Discovers, enriches, filters,
    searches, sorts, and paginates
    research sessions.
    """

    def __init__(

        self,

        session_manager,

        profile_store,

        branch_store,

        lineage_service,

    ):

        self.session_manager = (
            session_manager
        )

        self.profile_store = (
            profile_store
        )

        self.branch_store = (
            branch_store
        )

        self.lineage_service = (
            lineage_service
        )

    @staticmethod
    def _as_naive_utc(

        timestamp,

    ):

        if (

            timestamp is not None

            and timestamp.tzinfo
            is not None
        ):

            return (

                timestamp
                .astimezone(
                    timezone.utc
                )
                .replace(
                    tzinfo=None,
                )
            )

        return timestamp

    def _session_created_at(

        self,

        session,

        profile,

    ):

        if profile is not None:

            return (

                self._as_naive_utc(

                    profile.created_at
                )
            )

        created_at = getattr(

            session,

            "created_at",

            None,
        )

        if created_at is not None:

            return created_at

        return session.updated_at

    def _session_updated_at(

        self,

        session,

        profile,

    ):

        timestamps = [

            timestamp

            for timestamp in [

                getattr(
                    session,
                    "updated_at",
                    None,
                ),

                self._as_naive_utc(

                    profile.updated_at

                    if profile

                    else None
                ),
            ]

            if timestamp is not None
        ]

        return max(
            timestamps
        )

    def _build_item(

        self,

        session,

    ):

        session_id = (
            session.session_id
        )

        profile = (

            self.profile_store
            .get(

                session_id
            )
        )

        origin = (

            self.branch_store
            .get_by_branch_session(

                session_id
            )
        )

        kind = (

            ResearchSessionKind
            .BRANCH

            if origin is not None

            else (

                ResearchSessionKind
                .ROOT
            )
        )

        summary = (

            self.lineage_service
            .summarize(

                session_id
            )
        )

        display_name = (

            profile.display_name

            if (

                profile is not None

                and

                profile.display_name
            )

            else (

                getattr(

                    session,

                    "paper_title",

                    None,
                )

                or session_id
            )
        )

        status = (

            profile.status

            if profile is not None

            else (

                ResearchSessionStatus
                .ACTIVE
            )
        )

        archived = (

            profile.archived

            if profile is not None

            else False
        )

        description = (

            profile.description

            if profile is not None

            else None
        )

        return (

            ResearchSessionListItem(

                session_id=(
                    session_id
                ),

                display_name=(
                    display_name
                ),

                description=(
                    description
                ),

                paper_id=getattr(

                    session,

                    "paper_id",

                    None,
                ),

                paper_title=getattr(

                    session,

                    "paper_title",

                    None,
                ),

                status=status,

                archived=archived,

                kind=kind,

                parent_session_id=(

                    summary
                    .parent_session_id
                ),

                root_session_id=(

                    summary
                    .root_session_id
                ),

                depth=(
                    summary.depth
                ),

                child_count=(
                    summary.child_count
                ),

                descendant_count=(

                    summary
                    .descendant_count
                ),

                created_at=(

                    self
                    ._session_created_at(

                        session,

                        profile,
                    )
                ),

                updated_at=(

                    self
                    ._session_updated_at(

                        session,

                        profile,
                    )
                ),
            )
        )

    def query(

        self,

        query,

    ) -> ResearchSessionPage:

        sessions = (

            self.session_manager
            .list_sessions()
        )

        items = [

            self._build_item(
                session
            )

            for session

            in sessions
        ]

        items = self._filter_statuses(

            items,

            query.statuses,
        )

        items = self._filter_archived(

            items,

            query.archived,
        )

        items = self._filter_kinds(

            items,

            query.kinds,
        )

        items = self._filter_lineage_root(

            items,

            query.lineage_root_session_id,
        )

        items = self._filter_direct_parent(

            items,

            query.direct_parent_session_id,
        )

        items = self._filter_search(

            items,

            query.search,
        )

        items = self._sort(

            items,

            query.sort_order,
        )

        total = len(
            items
        )

        page_items = items[

            query.offset:

            query.offset
            + query.limit
        ]

        return (

            ResearchSessionPage(

                items=page_items,

                total=total,

                offset=query.offset,

                limit=query.limit,
            )
        )

    def _filter_statuses(

        self,

        items,

        statuses,

    ):

        if not statuses:

            return items

        return [

            item

            for item

            in items

            if item.status in statuses
        ]

    def _filter_archived(

        self,

        items,

        archived,

    ):

        if archived is None:

            return items

        return [

            item

            for item

            in items

            if item.archived is archived
        ]

    def _filter_kinds(

        self,

        items,

        kinds,

    ):

        if not kinds:

            return items

        return [

            item

            for item

            in items

            if item.kind in kinds
        ]

    def _filter_lineage_root(

        self,

        items,

        lineage_root_session_id,

    ):

        if lineage_root_session_id is None:

            return items

        return [

            item

            for item

            in items

            if (

                item.root_session_id

                == lineage_root_session_id
            )
        ]

    def _filter_direct_parent(

        self,

        items,

        direct_parent_session_id,

    ):

        if direct_parent_session_id is None:

            return items

        return [

            item

            for item

            in items

            if (

                item.parent_session_id

                == direct_parent_session_id
            )
        ]

    def _filter_search(

        self,

        items,

        search,

    ):

        if search is None:

            return items

        normalized = (
            search.casefold()
        )

        matching = []

        for item in items:

            searchable_values = [

                item.session_id,

                item.display_name,

                item.description,

                item.paper_id,

                item.paper_title,

                item.status.value,

                item.kind.value,
            ]

            searchable_text = " ".join(

                str(value)

                for value

                in searchable_values

                if value is not None
            ).casefold()

            if normalized in searchable_text:

                matching.append(
                    item
                )

        return matching

    def _sort(

        self,

        items,

        sort_order,

    ):

        if (

            sort_order

            == (
                ResearchSessionSortOrder
                .CREATED_NEWEST
            )
        ):

            return sorted(

                items,

                key=lambda item: (

                    item.created_at,

                    item.session_id,
                ),

                reverse=True,
            )

        if (

            sort_order

            == (
                ResearchSessionSortOrder
                .CREATED_OLDEST
            )
        ):

            return sorted(

                items,

                key=lambda item: (

                    item.created_at,

                    item.session_id,
                ),
            )

        if (

            sort_order

            == (
                ResearchSessionSortOrder
                .UPDATED_NEWEST
            )
        ):

            return sorted(

                items,

                key=lambda item: (

                    item.updated_at,

                    item.session_id,
                ),

                reverse=True,
            )

        if (

            sort_order

            == (
                ResearchSessionSortOrder
                .UPDATED_OLDEST
            )
        ):

            return sorted(

                items,

                key=lambda item: (

                    item.updated_at,

                    item.session_id,
                ),
            )

        if (

            sort_order

            == (
                ResearchSessionSortOrder
                .NAME_ASCENDING
            )
        ):

            return sorted(

                items,

                key=lambda item: (

                    item.display_name
                    .casefold(),

                    item.session_id,
                ),
            )

        return sorted(

            items,

            key=lambda item: (

                item.display_name
                .casefold(),

                item.session_id,
            ),

            reverse=True,
        )
