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

from .research_workspace_consumer_projection_execution_coordinator import (
    ResearchWorkspaceConsumerProjectionExecutionCoordinator,
)

from .research_workspace_consumer_projection_freshness_status import (
    ResearchWorkspaceConsumerProjectionFreshnessStatus,
)

from .research_workspace_consumer_projection_unusable_freshness_error import (
    ResearchWorkspaceConsumerProjectionUnusableFreshnessError,
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

        provenance=None,

        budget=None,

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
                    provenance=provenance,
                )
            )

        coordinator = (

            ResearchWorkspaceConsumerProjectionExecutionCoordinator(

                budget=budget,

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

            coordinator.execute_stage(

                name=(
                    "workspace.bootstrap.overview"
                ),

                operation=(

                    lambda: (

                        self._load_overview(

                            context,

                            diagnostics,
                        )
                    )
                ),
            )
        )

        attention = (

            coordinator.execute_stage(

                name=(
                    "workspace.attention.project"
                ),

                operation=(

                    lambda: (

                        self._load_attention_summary(

                            context,

                            diagnostics,

                            provenance,

                            warnings,
                        )
                    )
                ),

                on_skip=(

                    lambda: (

                        self._skip_attention_summary(
                            warnings
                        )
                    )
                ),
            )
        )

        workspace_actions = (

            coordinator.execute_stage(

                name=(
                    "workspace.actions.project"
                ),

                operation=(

                    lambda: (

                        self._load_workspace_actions(

                            context,

                            diagnostics,

                            warnings,
                        )
                    )
                ),

                on_skip=(

                    lambda: (

                        self._skip_workspace_actions(
                            warnings
                        )
                    )
                ),
            )
        )

        recent_sessions = (

            coordinator.execute_stage(

                name=(
                    "workspace.bootstrap.recent_sessions"
                ),

                operation=(

                    lambda: (

                        self._load_recent_sessions(

                            recent_session_limit,

                            diagnostics,

                            warnings,
                        )
                    )
                ),

                on_skip=(

                    lambda: (

                        self._skip_recent_sessions(
                            warnings
                        )
                    )
                ),
            )
        )

        recent_activity = (

            coordinator.execute_stage(

                name=(
                    "workspace.bootstrap.recent_activity"
                ),

                operation=(

                    lambda: (

                        self._load_recent_activity(

                            recent_activity_limit,

                            context,

                            diagnostics,

                            warnings,
                        )
                    )
                ),

                on_skip=(

                    lambda: (

                        self._skip_recent_activity(
                            warnings
                        )
                    )
                ),
            )
        )

        return (

            coordinator.execute_stage(

                name=(
                    "workspace.bootstrap.assemble"
                ),

                operation=(

                    lambda: (

                        self._assemble(

                            context,

                            diagnostics,

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
                ),
            )
        )

    def _assemble(

        self,

        context,

        diagnostics,

        *,

        capabilities,

        readiness,

        overview,

        attention,

        workspace_actions,

        recent_sessions,

        recent_activity,

        warnings,

    ):

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

    @staticmethod
    def _skip_attention_summary(

        warnings,

    ):

        warnings.append(
            "Attention summary was "
            "skipped due to the "
            "execution budget."
        )

        return (
            ResearchWorkspaceAttentionSummary()
        )

    @staticmethod
    def _skip_workspace_actions(

        warnings,

    ):

        warnings.append(
            "Workspace actions were "
            "skipped due to the "
            "execution budget."
        )

        return []

    @staticmethod
    def _skip_recent_sessions(

        warnings,

    ):

        warnings.append(
            "Recent sessions were "
            "skipped due to the "
            "execution budget."
        )

        return []

    @staticmethod
    def _skip_recent_activity(

        warnings,

    ):

        warnings.append(
            "Recent activity was "
            "skipped due to the "
            "execution budget."
        )

        return []

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

        provenance,

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

                    provenance=(
                        provenance
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

        context,

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

            freshness = None

            try:

                freshness = (

                    context
                    .get_recent_activity_freshness()
                )

            except ResearchWorkspaceConsumerProjectionUnusableFreshnessError:

                warnings.append(
                    "Recent activity data "
                    "is too stale to use."
                )

                stage.mark_degraded(
                    reason_code=(
                        "source_data_unusable_due_to_staleness"
                    ),
                )

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

                stage.mark_degraded(
                    reason_code=(
                        "recent_activity_unavailable"
                    ),
                )

                return []

            if (

                freshness is not None

                and freshness.status

                == ResearchWorkspaceConsumerProjectionFreshnessStatus
                .STALE
            ):

                stage.mark_degraded(
                    reason_code=(
                        "stale_source_used"
                    ),
                )

            return list(
                page.items
            )
