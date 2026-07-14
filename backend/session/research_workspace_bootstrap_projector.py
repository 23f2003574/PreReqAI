from .research_session_query import (
    ResearchSessionQuery,
)

from .research_session_sort_order import (
    ResearchSessionSortOrder,
)

from .research_workspace_attention_summary import (
    ResearchWorkspaceAttentionSummary,
)

from .research_workspace_bootstrap_projection import (
    ResearchWorkspaceBootstrapProjection,
)

from .research_workspace_consumer_projection_diagnostic_stage_kind import (
    ResearchWorkspaceConsumerProjectionDiagnosticStageKind,
)

from .research_workspace_consumer_projection_diagnostics_stage_helper import (
    stage_or_noop,
)


_ATTENTION_PREVIEW_LIMIT = 3


class ResearchWorkspaceBootstrapProjector:
    """
    Assembles a bounded, frontend-ready
    startup context from the existing
    capability, readiness, insights,
    discovery, activity, and attention
    systems.
    """

    def __init__(

        self,

        context_factory,

        discovery_service,

        activity_service,

        attention_projector,

        action_projector,

    ):

        self.context_factory = (
            context_factory
        )

        self.discovery_service = (
            discovery_service
        )

        self.activity_service = (
            activity_service
        )

        self.attention_projector = (
            attention_projector
        )

        self.action_projector = (
            action_projector
        )

    def project(

        self,

        *,

        context=None,

        diagnostics=None,

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

        if context is None:

            context = (

                self.context_factory
                .create(
                    diagnostics=diagnostics,
                )
            )

        warnings = []

        capabilities = (

            context.get_capabilities()
        )

        readiness = (

            context.get_readiness()
        )

        overview = (

            self._load_overview(
                context,

                diagnostics,
            )
        )

        attention = (

            self._load_attention_summary(

                context,

                diagnostics,

                warnings,
            )
        )

        workspace_actions = (

            self._load_workspace_actions(

                context,

                diagnostics,

                warnings,
            )
        )

        recent_sessions = (

            self._load_recent_sessions(

                recent_session_limit,

                diagnostics,

                warnings,
            )
        )

        recent_activity = (

            self._load_recent_activity(

                recent_activity_limit,

                diagnostics,

                warnings,
            )
        )

        with stage_or_noop(

            diagnostics,

            "workspace.bootstrap.assemble",

            ResearchWorkspaceConsumerProjectionDiagnosticStageKind
            .ASSEMBLY,
        ):

            return (

                ResearchWorkspaceBootstrapProjection(

                    capabilities=capabilities,

                    readiness=readiness,

                    overview=overview,

                    attention=attention,

                    workspace_actions=(
                        workspace_actions
                    ),

                    recent_sessions=(
                        recent_sessions
                    ),

                    recent_activity=(
                        recent_activity
                    ),

                    warnings=warnings,
                )
            )

    def _load_overview(

        self,

        context,

        diagnostics,

    ):

        with stage_or_noop(

            diagnostics,

            "workspace.bootstrap.overview",

            ResearchWorkspaceConsumerProjectionDiagnosticStageKind
            .ASSEMBLY,
        ):

            return (

                context
                .get_workspace_insights()
                .overview
            )

    def _load_attention_summary(

        self,

        context,

        diagnostics,

        warnings,

    ):

        try:

            projection = (

                self.attention_projector
                .project(

                    context=context,

                    diagnostics=(
                        diagnostics
                    ),
                )
            )

        except Exception:

            warnings.append(
                "Attention summary could "
                "not be computed."
            )

            return (
                ResearchWorkspaceAttentionSummary()
            )

        return (

            ResearchWorkspaceAttentionSummary(

                total_count=(
                    projection.total_count
                ),

                actionable_count=(
                    projection.actionable_count
                ),

                critical_count=(
                    projection.critical_count
                ),

                high_count=(
                    projection.high_count
                ),

                top_items=list(

                    projection.items[
                        :_ATTENTION_PREVIEW_LIMIT
                    ]
                ),
            )
        )

    def _load_workspace_actions(

        self,

        context,

        diagnostics,

        warnings,

    ):

        try:

            projection = (

                self.action_projector
                .project_workspace_actions(

                    context=context,

                    diagnostics=(
                        diagnostics
                    ),
                )
            )

        except Exception:

            warnings.append(
                "Workspace actions could "
                "not be loaded."
            )

            return []

        return list(
            projection.actions
        )

    def _load_recent_sessions(

        self,

        limit,

        diagnostics,

        warnings,

    ):

        if limit == 0:

            return []

        with stage_or_noop(

            diagnostics,

            "workspace.bootstrap.recent_sessions",

            ResearchWorkspaceConsumerProjectionDiagnosticStageKind
            .ASSEMBLY,

        ) as stage:

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

                stage.mark_degraded(
                    reason_code=(
                        "recent_sessions_unavailable"
                    ),
                )

                return []

            return list(
                page.items
            )

    def _load_recent_activity(

        self,

        limit,

        diagnostics,

        warnings,

    ):

        if limit == 0:

            return []

        with stage_or_noop(

            diagnostics,

            "workspace.bootstrap.recent_activity",

            ResearchWorkspaceConsumerProjectionDiagnosticStageKind
            .ASSEMBLY,

        ) as stage:

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

                stage.mark_degraded(
                    reason_code=(
                        "recent_activity_unavailable"
                    ),
                )

                return []

            return list(
                page.items
            )
