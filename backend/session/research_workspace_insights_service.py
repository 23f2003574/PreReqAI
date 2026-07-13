from collections import (
    Counter,
)

from datetime import (
    datetime,
    timedelta,
    timezone,
)

from .research_activity_statistics import (
    ResearchActivityStatistics,
)

from .research_collection_statistic import (
    ResearchCollectionStatistic,
)

from .research_lifecycle_statistics import (
    ResearchLifecycleStatistics,
)

from .research_lineage_statistics import (
    ResearchLineageStatistics,
)

from .research_session_activity_summary import (
    ResearchSessionActivitySummary,
)

from .research_tag_statistic import (
    ResearchTagStatistic,
)

from .research_workspace_insights import (
    ResearchWorkspaceInsights,
)

from .research_workspace_overview import (
    ResearchWorkspaceOverview,
)


_ACTIVE_LIKE_STATUSES = {

    "active",

    "paused",
}


class ResearchWorkspaceInsightsService:
    """
    Derives workspace-level research
    analytics from canonical domain stores.
    """

    def __init__(

        self,

        session_manager,

        profile_store,

        lineage_service,

        tag_store,

        collection_store,

        activity_store,

        clock=None,

    ):

        self.session_manager = (
            session_manager
        )

        self.profile_store = (
            profile_store
        )

        self.lineage_service = (
            lineage_service
        )

        self.tag_store = (
            tag_store
        )

        self.collection_store = (
            collection_store
        )

        self.activity_store = (
            activity_store
        )

        self.clock = (
            clock
        )

    def _now(self):

        if self.clock is not None:

            return self.clock()

        return datetime.now(
            timezone.utc
        )

    def _session_ids(self):

        sessions = (

            self.session_manager
            .list_sessions()
        )

        return [

            session.session_id

            for session

            in sessions
        ]

    def _build_overview(

        self,

        session_ids,

        profiles,

        branch_session_ids,

        events,

    ):

        archived_count = sum(

            1

            for session_id

            in session_ids

            if (

                profiles.get(
                    session_id
                )

                is not None

                and profiles[
                    session_id
                ].archived
            )
        )

        total_sessions = len(
            session_ids
        )

        return (

            ResearchWorkspaceOverview(

                total_sessions=(
                    total_sessions
                ),

                archived_sessions=(
                    archived_count
                ),

                unarchived_sessions=(

                    total_sessions

                    - archived_count
                ),

                root_sessions=(

                    total_sessions

                    - len(
                        branch_session_ids
                    )
                ),

                branch_sessions=(
                    len(
                        branch_session_ids
                    )
                ),

                total_tags=(

                    len(

                        self.tag_store
                        .list_tags()
                    )
                ),

                total_collections=(

                    len(

                        self.collection_store
                        .list_collections()
                    )
                ),

                total_activity_events=(
                    len(
                        events
                    )
                ),
            )
        )

    def _build_lifecycle_statistics(

        self,

        session_ids,

        profiles,

    ):

        counts = Counter()

        for session_id in session_ids:

            profile = (

                profiles.get(
                    session_id
                )
            )

            if profile is None:

                counts[
                    "unknown"
                ] += 1

                continue

            counts[
                profile.status.value
            ] += 1

        return (

            ResearchLifecycleStatistics(

                counts=dict(
                    counts
                )
            )
        )

    def _build_lineage_statistics(

        self,

        session_ids,

        parents,

    ):

        if not session_ids:

            return (

                ResearchLineageStatistics(

                    total_roots=0,

                    total_branches=0,

                    maximum_depth=0,

                    average_depth=0.0,

                    deepest_session_id=None,

                    most_branched_session_id=None,

                    most_branched_direct_children=0,
                )
            )

        branch_session_ids = {

            session_id

            for session_id, parent

            in parents.items()

            if parent is not None
        }

        root_ids = [

            session_id

            for session_id

            in session_ids

            if (

                session_id

                not in branch_session_ids
            )
        ]

        depths = {

            session_id: (

                self.lineage_service
                .depth(

                    session_id
                )
            )

            for session_id

            in session_ids
        }

        deepest_session_id = max(

            depths,

            key=lambda session_id: (

                depths[
                    session_id
                ],

                session_id,
            ),
        )

        direct_child_counts = Counter(

            parent

            for parent

            in parents.values()

            if parent is not None
        )

        if direct_child_counts:

            most_branched_session_id = max(

                direct_child_counts,

                key=lambda session_id: (

                    direct_child_counts[
                        session_id
                    ],

                    session_id,
                ),
            )

            most_branched_count = (

                direct_child_counts[
                    most_branched_session_id
                ]
            )

        else:

            most_branched_session_id = None

            most_branched_count = 0

        return (

            ResearchLineageStatistics(

                total_roots=(
                    len(
                        root_ids
                    )
                ),

                total_branches=(
                    len(
                        branch_session_ids
                    )
                ),

                maximum_depth=(
                    max(
                        depths.values()
                    )
                ),

                average_depth=(

                    sum(
                        depths.values()
                    )

                    / len(
                        depths
                    )
                ),

                deepest_session_id=(
                    deepest_session_id
                ),

                most_branched_session_id=(
                    most_branched_session_id
                ),

                most_branched_direct_children=(
                    most_branched_count
                ),
            )
        )

    def _build_tag_statistics(

        self,

        limit,

    ):

        statistics = []

        for tag in (

            self.tag_store
            .list_tags()
        ):

            session_ids = (

                self.tag_store
                .list_session_ids_for_tag(

                    tag.id
                )
            )

            statistics.append(

                ResearchTagStatistic(

                    tag_id=(
                        tag.id
                    ),

                    tag_name=(
                        tag.name
                    ),

                    session_count=(
                        len(
                            session_ids
                        )
                    ),
                )
            )

        statistics.sort(

            key=lambda item: (

                -item.session_count,

                item.tag_name,

                item.tag_id,
            )
        )

        return statistics[
            :limit
        ]

    def _build_collection_statistics(

        self,

        limit,

    ):

        statistics = []

        for collection in (

            self.collection_store
            .list_collections()
        ):

            session_ids = (

                self.collection_store
                .list_session_ids(

                    collection.id
                )
            )

            statistics.append(

                ResearchCollectionStatistic(

                    collection_id=(
                        collection.id
                    ),

                    collection_name=(
                        collection.name
                    ),

                    session_count=(
                        len(
                            session_ids
                        )
                    ),
                )
            )

        statistics.sort(

            key=lambda item: (

                -item.session_count,

                item.collection_name,

                item.collection_id,
            )
        )

        return statistics[
            :limit
        ]

    def _build_activity_statistics(

        self,

        events,

        now,

    ):

        last_24_hours = (

            now

            - timedelta(
                hours=24
            )
        )

        last_7_days = (

            now

            - timedelta(
                days=7
            )
        )

        last_30_days = (

            now

            - timedelta(
                days=30
            )
        )

        counts_by_type = Counter(

            event.activity_type.value

            for event

            in events
        )

        return (

            ResearchActivityStatistics(

                total_events=(
                    len(
                        events
                    )
                ),

                events_last_24_hours=(

                    sum(

                        1

                        for event

                        in events

                        if (

                            event.occurred_at

                            >= last_24_hours
                        )
                    )
                ),

                events_last_7_days=(

                    sum(

                        1

                        for event

                        in events

                        if (

                            event.occurred_at

                            >= last_7_days
                        )
                    )
                ),

                events_last_30_days=(

                    sum(

                        1

                        for event

                        in events

                        if (

                            event.occurred_at

                            >= last_30_days
                        )
                    )
                ),

                counts_by_type=(
                    dict(
                        counts_by_type
                    )
                ),
            )
        )

    @staticmethod
    def _build_session_activity_index(

        events,

    ):

        index = {}

        for event in events:

            related_ids = {

                event.session_id,

                event.related_session_id,
            }

            related_ids.discard(
                None
            )

            for session_id in (
                related_ids
            ):

                index.setdefault(

                    session_id,

                    [],
                ).append(
                    event
                )

        return index

    @staticmethod
    def _build_session_activity_summary(

        session_id,

        profile,

        events,

    ):

        last_activity_at = (

            max(

                (
                    event.occurred_at

                    for event

                    in events
                ),

                default=None,
            )
        )

        display_name = (

            profile.display_name

            if (

                profile is not None

                and profile.display_name
            )

            else session_id
        )

        lifecycle_status = (

            profile.status.value

            if profile is not None

            else "unknown"
        )

        archived = (

            profile.archived

            if profile is not None

            else False
        )

        return (

            ResearchSessionActivitySummary(

                session_id=(
                    session_id
                ),

                display_name=(
                    display_name
                ),

                lifecycle_status=(
                    lifecycle_status
                ),

                archived=(
                    archived
                ),

                last_activity_at=(
                    last_activity_at
                ),

                activity_count=(
                    len(
                        events
                    )
                ),
            )
        )

    def _build_recently_active_sessions(

        self,

        session_ids,

        profiles,

        activity_index,

        limit,

    ):

        summaries = [

            self._build_session_activity_summary(

                session_id=(
                    session_id
                ),

                profile=(
                    profiles.get(
                        session_id
                    )
                ),

                events=(
                    activity_index.get(

                        session_id,

                        [],
                    )
                ),
            )

            for session_id

            in session_ids
        ]

        summaries = [

            summary

            for summary

            in summaries

            if (

                summary.last_activity_at

                is not None
            )
        ]

        summaries.sort(

            key=lambda item: (

                item.last_activity_at,

                item.session_id,
            ),

            reverse=True,
        )

        return summaries[
            :limit
        ]

    def _build_dormant_sessions(

        self,

        session_ids,

        profiles,

        activity_index,

        now,

        dormant_after_days,

        limit,

    ):

        threshold = (

            now

            - timedelta(

                days=(
                    dormant_after_days
                )
            )
        )

        summaries = []

        for session_id in session_ids:

            profile = (

                profiles.get(
                    session_id
                )
            )

            if profile is None:

                continue

            if profile.archived:

                continue

            if (

                profile.status.value

                not in (
                    _ACTIVE_LIKE_STATUSES
                )
            ):

                continue

            summary = (

                self
                ._build_session_activity_summary(

                    session_id=(
                        session_id
                    ),

                    profile=(
                        profile
                    ),

                    events=(
                        activity_index.get(

                            session_id,

                            [],
                        )
                    ),
                )
            )

            if (

                summary.last_activity_at

                is None

                or

                summary.last_activity_at

                < threshold
            ):

                summaries.append(
                    summary
                )

        summaries.sort(

            key=lambda item: (

                item.last_activity_at
                is not None,

                item.last_activity_at
                or datetime.min.replace(

                    tzinfo=(
                        timezone.utc
                    )
                ),

                item.session_id,
            )
        )

        return summaries[
            :limit
        ]

    def build_insights(

        self,

        top_tag_limit=10,

        collection_limit=10,

        recent_session_limit=10,

        dormant_session_limit=10,

        dormant_after_days=30,

    ):

        now = self._now()

        session_ids = (
            self._session_ids()
        )

        profiles = {

            profile.session_id:
                profile

            for profile

            in self.profile_store
            .list_all()
        }

        parents = {

            session_id: (

                self.lineage_service
                .parent_session_id(

                    session_id
                )
            )

            for session_id

            in session_ids
        }

        branch_session_ids = {

            session_id

            for session_id, parent

            in parents.items()

            if parent is not None
        }

        events = (

            self.activity_store
            .list_all()
        )

        activity_index = (

            self._build_session_activity_index(

                events
            )
        )

        return (

            ResearchWorkspaceInsights(

                overview=(

                    self._build_overview(

                        session_ids=(
                            session_ids
                        ),

                        profiles=(
                            profiles
                        ),

                        branch_session_ids=(
                            branch_session_ids
                        ),

                        events=(
                            events
                        ),
                    )
                ),

                lifecycle=(

                    self
                    ._build_lifecycle_statistics(

                        session_ids=(
                            session_ids
                        ),

                        profiles=(
                            profiles
                        ),
                    )
                ),

                lineage=(

                    self._build_lineage_statistics(

                        session_ids=(
                            session_ids
                        ),

                        parents=(
                            parents
                        ),
                    )
                ),

                activity=(

                    self._build_activity_statistics(

                        events=(
                            events
                        ),

                        now=(
                            now
                        ),
                    )
                ),

                top_tags=(

                    self._build_tag_statistics(

                        limit=(
                            top_tag_limit
                        )
                    )
                ),

                largest_collections=(

                    self
                    ._build_collection_statistics(

                        limit=(
                            collection_limit
                        )
                    )
                ),

                recently_active_sessions=(

                    self
                    ._build_recently_active_sessions(

                        session_ids=(
                            session_ids
                        ),

                        profiles=(
                            profiles
                        ),

                        activity_index=(
                            activity_index
                        ),

                        limit=(
                            recent_session_limit
                        ),
                    )
                ),

                dormant_sessions=(

                    self._build_dormant_sessions(

                        session_ids=(
                            session_ids
                        ),

                        profiles=(
                            profiles
                        ),

                        activity_index=(
                            activity_index
                        ),

                        now=(
                            now
                        ),

                        dormant_after_days=(
                            dormant_after_days
                        ),

                        limit=(
                            dormant_session_limit
                        ),
                    )
                ),
            )
        )
