from .research_activity_page import (
    ResearchActivityPage,
)

from .research_activity_query import (
    ResearchActivityQuery,
)


class ResearchActivityService:
    """
    Provides unified research workspace
    activity timeline queries.
    """

    def __init__(

        self,

        activity_store,

    ):

        self.activity_store = (
            activity_store
        )

    def _filter_sessions(

        self,

        events,

        session_ids,

    ):

        if not session_ids:

            return events

        return [

            event

            for event

            in events

            if (

                event.session_id
                in session_ids

                or

                event.related_session_id
                in session_ids
            )
        ]

    def _filter_activity_types(

        self,

        events,

        activity_types,

    ):

        if not activity_types:

            return events

        return [

            event

            for event

            in events

            if (

                event.activity_type

                in activity_types
            )
        ]

    def _filter_actor_types(

        self,

        events,

        actor_types,

    ):

        if not actor_types:

            return events

        return [

            event

            for event

            in events

            if (

                event.actor_type

                in actor_types
            )
        ]

    def _filter_time_range(

        self,

        events,

        occurred_from,

        occurred_to,

    ):

        if occurred_from is not None:

            events = [

                event

                for event

                in events

                if (

                    event.occurred_at

                    >= occurred_from
                )
            ]

        if occurred_to is not None:

            events = [

                event

                for event

                in events

                if (

                    event.occurred_at

                    <= occurred_to
                )
            ]

        return events

    def query(

        self,

        query,

    ):

        events = (

            self.activity_store
            .list_all()
        )

        events = (

            self._filter_sessions(

                events,

                query.session_ids,
            )
        )

        events = (

            self._filter_activity_types(

                events,

                query.activity_types,
            )
        )

        events = (

            self._filter_actor_types(

                events,

                query.actor_types,
            )
        )

        events = (

            self._filter_time_range(

                events,

                query.occurred_from,

                query.occurred_to,
            )
        )

        events.sort(

            key=lambda event: (

                event.occurred_at,

                event.id,
            ),

            reverse=(
                query.newest_first
            ),
        )

        total = len(
            events
        )

        start = (

            (
                query.page - 1
            )

            * query.page_size
        )

        end = (

            start

            + query.page_size
        )

        return (

            ResearchActivityPage(

                items=events[
                    start:end
                ],

                page=(
                    query.page
                ),

                page_size=(
                    query.page_size
                ),

                total=total,
            )
        )

    def timeline_for_session(

        self,

        session_id,

        page=1,

        page_size=50,

    ):

        return self.query(

            ResearchActivityQuery(

                session_ids={
                    session_id
                },

                page=page,

                page_size=(
                    page_size
                ),

                newest_first=True,
            )
        )

    def recent_activity(

        self,

        page=1,

        page_size=50,

    ):

        return self.query(

            ResearchActivityQuery(

                page=page,

                page_size=(
                    page_size
                ),

                newest_first=True,
            )
        )
