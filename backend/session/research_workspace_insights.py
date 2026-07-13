from dataclasses import (
    dataclass,
    field,
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

from .research_workspace_overview import (
    ResearchWorkspaceOverview,
)


@dataclass
class ResearchWorkspaceInsights:
    """
    Complete derived analytics snapshot
    for the research workspace.
    """

    overview: (
        ResearchWorkspaceOverview
    )

    lifecycle: (
        ResearchLifecycleStatistics
    )

    lineage: (
        ResearchLineageStatistics
    )

    activity: (
        ResearchActivityStatistics
    )

    top_tags: list[
        ResearchTagStatistic
    ] = field(
        default_factory=list,
    )

    largest_collections: list[
        ResearchCollectionStatistic
    ] = field(
        default_factory=list,
    )

    recently_active_sessions: list[
        ResearchSessionActivitySummary
    ] = field(
        default_factory=list,
    )

    dormant_sessions: list[
        ResearchSessionActivitySummary
    ] = field(
        default_factory=list,
    )

    def to_dict(self):

        return {

            "overview":
                self.overview.to_dict(),

            "lifecycle":
                self.lifecycle.to_dict(),

            "lineage":
                self.lineage.to_dict(),

            "activity":
                self.activity.to_dict(),

            "top_tags": [

                item.to_dict()

                for item

                in self.top_tags
            ],

            "largest_collections": [

                item.to_dict()

                for item

                in self.largest_collections
            ],

            "recently_active_sessions": [

                item.to_dict()

                for item

                in self.recently_active_sessions
            ],

            "dormant_sessions": [

                item.to_dict()

                for item

                in self.dormant_sessions
            ],
        }
