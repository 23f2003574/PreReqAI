from .research_checkpoint_reason import (
    ResearchCheckpointReason,
)

from .research_history_page import (
    ResearchHistoryPage,
)

from .research_history_sort_order import (
    ResearchHistorySortOrder,
)

from .research_history_timeline_item import (
    ResearchHistoryTimelineItem,
)


class ResearchHistoryQueryService:
    """
    Queries, filters, searches, sorts,
    and paginates research checkpoint
    history.
    """

    RECOVERY_REASONS = {

        ResearchCheckpointReason
        .RECOVERY_SAFETY,

        ResearchCheckpointReason
        .CHECKPOINT_RESTORED,
    }

    def __init__(

        self,

        checkpoint_store,

        annotation_store,

    ):

        self.checkpoint_store = (
            checkpoint_store
        )

        self.annotation_store = (
            annotation_store
        )

    def query(

        self,

        session_id: str,

        query,

    ) -> ResearchHistoryPage:

        checkpoints = (

            self.checkpoint_store
            .list_for_session(

                session_id
            )
        )

        items = [

            ResearchHistoryTimelineItem(

                checkpoint=checkpoint,

                annotation=(

                    self.annotation_store
                    .get(

                        checkpoint.id
                    )
                ),
            )

            for checkpoint

            in checkpoints
        ]

        items = self._filter_reasons(

            items,

            query.reasons,
        )

        items = self._filter_pinned(

            items,

            query.pinned,
        )

        items = self._filter_recovery(

            items,

            query.recovery_only,
        )

        items = self._filter_created_from(

            items,

            query.created_from,
        )

        items = self._filter_created_until(

            items,

            query.created_until,
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

        return ResearchHistoryPage(

            items=page_items,

            total=total,

            offset=query.offset,

            limit=query.limit,
        )

    def _filter_reasons(

        self,

        items,

        reasons,

    ):

        if not reasons:

            return items

        return [

            item

            for item

            in items

            if item.reason in reasons
        ]

    def _filter_pinned(

        self,

        items,

        pinned,

    ):

        if pinned is None:

            return items

        return [

            item

            for item

            in items

            if item.pinned is pinned
        ]

    def _filter_recovery(

        self,

        items,

        recovery_only,

    ):

        if not recovery_only:

            return items

        return [

            item

            for item

            in items

            if (

                item.reason

                in self.RECOVERY_REASONS
            )
        ]

    def _filter_created_from(

        self,

        items,

        created_from,

    ):

        if created_from is None:

            return items

        return [

            item

            for item

            in items

            if (

                item.created_at

                >= created_from
            )
        ]

    def _filter_created_until(

        self,

        items,

        created_until,

    ):

        if created_until is None:

            return items

        return [

            item

            for item

            in items

            if (

                item.created_at

                <= created_until
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
            search.strip().casefold()
        )

        if not normalized:

            return items

        matching = []

        for item in items:

            searchable_values = [

                item.label,

                item.note,

                item.reason.value,
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

        reverse = (

            sort_order

            == (
                ResearchHistorySortOrder
                .NEWEST
            )
        )

        return sorted(

            items,

            key=lambda item: (

                item.created_at,

                item.id,
            ),

            reverse=reverse,
        )
