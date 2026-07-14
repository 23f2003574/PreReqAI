from .research_session_query import (
    ResearchSessionQuery,
)

from .research_session_sort_order import (
    ResearchSessionSortOrder,
)

from .research_workspace_bootstrap_projection import (
    ResearchWorkspaceBootstrapProjection,
)


class ResearchWorkspaceBootstrapProjector:
    """
    Assembles a bounded, frontend-ready
    startup context from the existing
    capability, readiness, insights,
    discovery, and activity systems.
    """

    def __init__(

        self,

        capability_registry,

        readiness_assessor,

        insights_service,

        discovery_service,

        activity_service,

    ):

        self.capability_registry = (
            capability_registry
        )

        self.readiness_assessor = (
            readiness_assessor
        )

        self.insights_service = (
            insights_service
        )

        self.discovery_service = (
            discovery_service
        )

        self.activity_service = (
            activity_service
        )

    def project(

        self,

        recent_session_limit=5,

        recent_activity_limit=10,

    ):

        if recent_session_limit < 0:

            raise ValueError(

                "Bootstrap recent session "
                "limit cannot be negative"
            )

        if recent_activity_limit < 0:

            raise ValueError(

                "Bootstrap recent activity "
                "limit cannot be negative"
            )

        warnings = []

        capabilities = (

            self.capability_registry
            .list_capabilities()
        )

        readiness = (

            self.readiness_assessor
            .assess()
        )

        overview = (

            self.insights_service
            .build_insights(

                top_tag_limit=0,

                collection_limit=0,

                recent_session_limit=0,

                dormant_session_limit=0,
            )
            .overview
        )

        recent_sessions = (

            self._load_recent_sessions(

                recent_session_limit,

                warnings,
            )
        )

        recent_activity = (

            self._load_recent_activity(

                recent_activity_limit,

                warnings,
            )
        )

        return (

            ResearchWorkspaceBootstrapProjection(

                capabilities=capabilities,

                readiness=readiness,

                overview=overview,

                recent_sessions=(
                    recent_sessions
                ),

                recent_activity=(
                    recent_activity
                ),

                warnings=warnings,
            )
        )

    def _load_recent_sessions(

        self,

        limit,

        warnings,

    ):

        if limit == 0:

            return []

        try:

            page = (

                self.discovery_service
                .query(

                    ResearchSessionQuery(

                        sort_order=(

                            ResearchSessionSortOrder
                            .UPDATED_NEWEST
                        ),

                        limit=limit,
                    )
                )
            )

        except Exception:

            warnings.append(
                "Recent sessions could "
                "not be loaded."
            )

            return []

        return list(
            page.items
        )

    def _load_recent_activity(

        self,

        limit,

        warnings,

    ):

        if limit == 0:

            return []

        try:

            page = (

                self.activity_service
                .recent_activity(

                    page=1,

                    page_size=limit,
                )
            )

        except Exception:

            warnings.append(
                "Recent activity could "
                "not be loaded."
            )

            return []

        return list(
            page.items
        )
