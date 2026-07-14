from .research_integrity_severity import (
    ResearchIntegritySeverity,
)

from .research_workspace_attention_category import (
    ResearchWorkspaceAttentionCategory,
)

from .research_workspace_attention_item import (
    ResearchWorkspaceAttentionItem,
)

from .research_workspace_attention_projection import (
    ResearchWorkspaceAttentionProjection,
)

from .research_workspace_attention_severity import (
    ResearchWorkspaceAttentionSeverity,
)

from .research_workspace_consumer_projection_diagnostic_stage_kind import (
    ResearchWorkspaceConsumerProjectionDiagnosticStageKind,
)

from .research_workspace_consumer_projection_diagnostics_stage_helper import (
    stage_or_noop,
)

from .research_workspace_readiness_status import (
    ResearchWorkspaceReadinessStatus,
)


_SEVERITY_RANK = {

    ResearchWorkspaceAttentionSeverity
    .INFO: 0,

    ResearchWorkspaceAttentionSeverity
    .LOW: 1,

    ResearchWorkspaceAttentionSeverity
    .MEDIUM: 2,

    ResearchWorkspaceAttentionSeverity
    .HIGH: 3,

    ResearchWorkspaceAttentionSeverity
    .CRITICAL: 4,
}


_INTEGRITY_SEVERITY_MAP = {

    ResearchIntegritySeverity
    .WARNING: (

        ResearchWorkspaceAttentionSeverity
        .MEDIUM
    ),

    ResearchIntegritySeverity
    .ERROR: (

        ResearchWorkspaceAttentionSeverity
        .HIGH
    ),

    ResearchIntegritySeverity
    .CRITICAL: (

        ResearchWorkspaceAttentionSeverity
        .CRITICAL
    ),
}


class ResearchWorkspaceAttentionProjector:
    """
    Derives a unified, read-only collection
    of actionable attention items from
    existing workspace readiness, integrity,
    and session signals.
    """

    def __init__(

        self,

        context_factory,

    ):

        self.context_factory = (
            context_factory
        )

    def project(

        self,

        *,

        context=None,

        diagnostics=None,

        category=None,

        minimum_severity=None,

        actionable_only=False,

        limit=None,

    ):

        if limit is not None and limit < 0:

            raise ValueError(

                "Attention limit cannot "
                "be negative"
            )

        if context is None:

            context = (

                self.context_factory
                .create(
                    diagnostics=diagnostics,
                )
            )

        with stage_or_noop(

            diagnostics,

            "workspace.attention.project",

            ResearchWorkspaceConsumerProjectionDiagnosticStageKind
            .PROJECTION,
        ):

            return (

                self._build_projection(

                    context,

                    category=category,

                    minimum_severity=(
                        minimum_severity
                    ),

                    actionable_only=(
                        actionable_only
                    ),

                    limit=limit,
                )
            )

    def _build_projection(

        self,

        context,

        *,

        category,

        minimum_severity,

        actionable_only,

        limit,

    ):

        readiness = (

            context.get_readiness()
        )

        items = []

        items.extend(
            self._readiness_items(
                readiness
            )
        )

        items.extend(
            self._integrity_items(
                context
            )
        )

        items.extend(
            self._stale_paused_session_items(
                context
            )
        )

        items = self._deduplicate(
            items
        )

        if category is not None:

            category = (

                self._normalize_category(
                    category
                )
            )

            items = [

                item

                for item

                in items

                if item.category == category
            ]

        if minimum_severity is not None:

            minimum_severity = (

                self._normalize_severity(
                    minimum_severity
                )
            )

            threshold = _SEVERITY_RANK[
                minimum_severity
            ]

            items = [

                item

                for item

                in items

                if (

                    _SEVERITY_RANK[
                        item.severity
                    ]

                    >= threshold
                )
            ]

        if actionable_only:

            items = [

                item

                for item

                in items

                if item.actionable
            ]

        items.sort(
            key=self._priority_key
        )

        if limit is not None:

            items = items[
                :limit
            ]

        return (

            ResearchWorkspaceAttentionProjection(

                items=items,

                total_count=len(
                    items
                ),

                actionable_count=(

                    sum(

                        1

                        for item

                        in items

                        if item.actionable
                    )
                ),

                critical_count=(

                    sum(

                        1

                        for item

                        in items

                        if (

                            item.severity

                            == ResearchWorkspaceAttentionSeverity
                            .CRITICAL
                        )
                    )
                ),

                high_count=(

                    sum(

                        1

                        for item

                        in items

                        if (

                            item.severity

                            == ResearchWorkspaceAttentionSeverity
                            .HIGH
                        )
                    )
                ),
            )
        )

    @staticmethod
    def _priority_key(

        item,

    ):

        return (

            -_SEVERITY_RANK[
                item.severity
            ],

            item.category.value,

            item.attention_id,
        )

    @staticmethod
    def _deduplicate(

        items,

    ):

        deduplicated = {}

        for item in items:

            deduplicated.setdefault(

                item.attention_id,

                item,
            )

        return list(
            deduplicated.values()
        )

    @staticmethod
    def _normalize_category(

        category,

    ):

        if isinstance(

            category,

            ResearchWorkspaceAttentionCategory,
        ):

            return category

        return (

            ResearchWorkspaceAttentionCategory(
                category
            )
        )

    @staticmethod
    def _normalize_severity(

        severity,

    ):

        if isinstance(

            severity,

            ResearchWorkspaceAttentionSeverity,
        ):

            return severity

        return (

            ResearchWorkspaceAttentionSeverity(
                severity
            )
        )

    def _readiness_items(

        self,

        readiness,

    ):

        if (

            readiness.status

            == ResearchWorkspaceReadinessStatus
            .DEGRADED
        ):

            message = (

                readiness.warnings[0]

                if readiness.warnings

                else (
                    "One or more workspace "
                    "conditions require "
                    "attention."
                )
            )

            return [

                ResearchWorkspaceAttentionItem(

                    attention_id=(
                        "readiness:degraded"
                    ),

                    category=(

                        ResearchWorkspaceAttentionCategory
                        .READINESS
                    ),

                    severity=(

                        ResearchWorkspaceAttentionSeverity
                        .MEDIUM
                    ),

                    title=(
                        "Workspace is operating "
                        "in degraded mode"
                    ),

                    message=message,

                    actionable=True,

                    action=(
                        "review_workspace_readiness"
                    ),

                    entity_type="workspace",

                    entity_id=None,

                    source=(
                        "workspace_readiness"
                    ),
                )
            ]

        if (

            readiness.status

            == ResearchWorkspaceReadinessStatus
            .UNAVAILABLE
        ):

            message = (

                readiness.blocking_reasons[0]

                if readiness.blocking_reasons

                else (
                    "Core research workspace "
                    "could not be accessed."
                )
            )

            return [

                ResearchWorkspaceAttentionItem(

                    attention_id=(
                        "readiness:unavailable"
                    ),

                    category=(

                        ResearchWorkspaceAttentionCategory
                        .READINESS
                    ),

                    severity=(

                        ResearchWorkspaceAttentionSeverity
                        .CRITICAL
                    ),

                    title=(
                        "Research workspace "
                        "is unavailable"
                    ),

                    message=message,

                    actionable=True,

                    action=(
                        "review_workspace_readiness"
                    ),

                    entity_type="workspace",

                    entity_id=None,

                    source=(
                        "workspace_readiness"
                    ),
                )
            ]

        return []

    def _integrity_items(

        self,

        context,

    ):

        report = (

            context
            .get_integrity_report()
        )

        items = []

        for finding in report.findings:

            severity = (

                _INTEGRITY_SEVERITY_MAP
                .get(
                    finding.severity
                )
            )

            if severity is None:

                continue

            entity_suffix = (

                finding.entity_id

                or "workspace"
            )

            items.append(

                ResearchWorkspaceAttentionItem(

                    attention_id=(

                        "integrity:"
                        f"{finding.code}:"
                        f"{entity_suffix}"
                    ),

                    category=(

                        ResearchWorkspaceAttentionCategory
                        .INTEGRITY
                    ),

                    severity=severity,

                    title=(
                        "Workspace integrity "
                        "issue detected"
                    ),

                    message=(
                        finding.message
                    ),

                    actionable=True,

                    action=(
                        "review_integrity"
                    ),

                    entity_type=(
                        finding.entity_type
                    ),

                    entity_id=(
                        finding.entity_id
                    ),

                    source=(
                        "workspace_integrity"
                    ),
                )
            )

        return items

    def _stale_paused_session_items(

        self,

        context,

    ):

        insights = (

            context
            .get_workspace_insights()
        )

        items = []

        for summary in (

            insights.dormant_sessions
        ):

            if (

                summary.lifecycle_status

                != "paused"
            ):

                continue

            items.append(

                ResearchWorkspaceAttentionItem(

                    attention_id=(
                        "research_session:"
                        "stale_paused:"
                        f"{summary.session_id}"
                    ),

                    category=(

                        ResearchWorkspaceAttentionCategory
                        .RESEARCH_SESSION
                    ),

                    severity=(

                        ResearchWorkspaceAttentionSeverity
                        .LOW
                    ),

                    title=(
                        "Paused research session "
                        "may need review"
                    ),

                    message=(

                        f'"{summary.display_name}" '
                        "has remained paused with "
                        "no recent activity."
                    ),

                    actionable=True,

                    action=(
                        "review_research_session"
                    ),

                    entity_type=(
                        "research_session"
                    ),

                    entity_id=(
                        summary.session_id
                    ),

                    source=(
                        "workspace_sessions"
                    ),
                )
            )

        return items
