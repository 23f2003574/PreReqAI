from .research_session_status import (
    ResearchSessionStatus,
)

from .research_workspace_action import (
    ResearchWorkspaceAction,
)

from .research_workspace_action_availability import (
    ResearchWorkspaceActionAvailability,
)

from .research_workspace_action_projection import (
    ResearchWorkspaceActionProjection,
)

from .research_workspace_action_scope import (
    ResearchWorkspaceActionScope,
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


_DIAGNOSTIC_ACTIONS = {

    ResearchWorkspaceAction
    .REVIEW_INTEGRITY,

    ResearchWorkspaceAction
    .PREVIEW_REPAIR_PLAN,

    ResearchWorkspaceAction
    .VIEW_ACTIVITY,

    ResearchWorkspaceAction
    .VIEW_INSIGHTS,

    ResearchWorkspaceAction
    .REVIEW_READINESS,

    ResearchWorkspaceAction
    .VIEW_LINEAGE,

    ResearchWorkspaceAction
    .COMPARE_SESSION,
}


_WORKSPACE_ACTION_ORDER = [

    ResearchWorkspaceAction
    .CREATE_SESSION,

    ResearchWorkspaceAction
    .IMPORT_SNAPSHOT,

    ResearchWorkspaceAction
    .EXPORT_SNAPSHOT,

    ResearchWorkspaceAction
    .REVIEW_READINESS,

    ResearchWorkspaceAction
    .REVIEW_INTEGRITY,

    ResearchWorkspaceAction
    .PREVIEW_REPAIR_PLAN,

    ResearchWorkspaceAction
    .VIEW_ACTIVITY,

    ResearchWorkspaceAction
    .VIEW_INSIGHTS,
]


_SESSION_ACTION_ORDER = [

    ResearchWorkspaceAction
    .CREATE_CHECKPOINT,

    ResearchWorkspaceAction
    .CREATE_BRANCH,

    ResearchWorkspaceAction
    .PAUSE_SESSION,

    ResearchWorkspaceAction
    .RESUME_SESSION,

    ResearchWorkspaceAction
    .COMPLETE_SESSION,

    ResearchWorkspaceAction
    .MANAGE_TAGS,

    ResearchWorkspaceAction
    .MANAGE_COLLECTIONS,

    ResearchWorkspaceAction
    .VIEW_LINEAGE,

    ResearchWorkspaceAction
    .COMPARE_SESSION,

    ResearchWorkspaceAction
    .ARCHIVE_SESSION,

    ResearchWorkspaceAction
    .RESTORE_SESSION,
]


class ResearchWorkspaceActionProjector:
    """
    Evaluates context-aware availability
    for known workspace actions using
    existing capability, readiness, and
    session state.
    """

    def __init__(

        self,

        action_catalog,

        context_factory,

    ):

        self.action_catalog = (
            action_catalog
        )

        self.context_factory = (
            context_factory
        )

    def project_workspace_actions(

        self,

        *,

        context=None,

        diagnostics=None,

        include_unavailable=False,

        mutating_only=False,

    ):

        if context is None:

            context = (

                self.context_factory
                .create(
                    diagnostics=diagnostics,
                )
            )

        with stage_or_noop(

            diagnostics,

            "workspace.actions.project",

            ResearchWorkspaceConsumerProjectionDiagnosticStageKind
            .PROJECTION,
        ):

            return (

                self._build_workspace_actions_projection(

                    context,

                    include_unavailable=(
                        include_unavailable
                    ),

                    mutating_only=(
                        mutating_only
                    ),
                )
            )

    def _build_workspace_actions_projection(

        self,

        context,

        *,

        include_unavailable,

        mutating_only,

    ):

        capabilities = (

            context.get_capabilities()
        )

        readiness = (

            context.get_readiness()
        )

        descriptors = (

            self._ordered_descriptors(

                ResearchWorkspaceActionScope
                .WORKSPACE,

                _WORKSPACE_ACTION_ORDER,
            )
        )

        availabilities = [

            self._evaluate_workspace_action(

                descriptor,

                capabilities,

                readiness,
            )

            for descriptor

            in descriptors
        ]

        return (

            self._build_projection(

                ResearchWorkspaceActionScope
                .WORKSPACE,

                None,

                availabilities,

                include_unavailable,

                mutating_only,
            )
        )

    def project_session_actions(

        self,

        session_id,

        *,

        context=None,

        diagnostics=None,

        include_unavailable=False,

        mutating_only=False,

    ):

        if context is None:

            context = (

                self.context_factory
                .create(
                    diagnostics=diagnostics,
                )
            )

        with stage_or_noop(

            diagnostics,

            "session.actions.project",

            ResearchWorkspaceConsumerProjectionDiagnosticStageKind
            .PROJECTION,
        ):

            return (

                self._build_session_actions_projection(

                    session_id,

                    context,

                    include_unavailable=(
                        include_unavailable
                    ),

                    mutating_only=(
                        mutating_only
                    ),
                )
            )

    def _build_session_actions_projection(

        self,

        session_id,

        context,

        *,

        include_unavailable,

        mutating_only,

    ):

        session = (

            context.get_session(
                session_id
            )
        )

        if session is None:

            raise ValueError(

                "Research session does "
                f"not exist: {session_id}"
            )

        capabilities = (

            context.get_capabilities()
        )

        readiness = (

            context.get_readiness()
        )

        profile = (

            context.get_session_profile(
                session_id
            )
        )

        status = (

            profile.status

            if profile is not None

            else ResearchSessionStatus
            .ACTIVE
        )

        archived = (

            profile.archived

            if profile is not None

            else False
        )

        descriptors = (

            self._ordered_descriptors(

                ResearchWorkspaceActionScope
                .SESSION,

                _SESSION_ACTION_ORDER,
            )
        )

        availabilities = [

            self._evaluate_session_action(

                descriptor,

                capabilities,

                readiness,

                status,

                archived,
            )

            for descriptor

            in descriptors
        ]

        return (

            self._build_projection(

                ResearchWorkspaceActionScope
                .SESSION,

                session_id,

                availabilities,

                include_unavailable,

                mutating_only,
            )
        )

    def _ordered_descriptors(

        self,

        scope,

        order,

    ):

        descriptors = (

            self.action_catalog
            .list_by_scope(
                scope
            )
        )

        index = {

            action: position

            for position, action

            in enumerate(
                order
            )
        }

        return sorted(

            descriptors,

            key=lambda descriptor: (

                index.get(

                    descriptor.action,

                    len(
                        order
                    ),
                )
            ),
        )

    @staticmethod
    def _capability_supported(

        capabilities,

        capability,

    ):

        for descriptor in capabilities:

            if (

                descriptor.name

                == capability.value
            ):

                return descriptor.enabled

        return False

    def _capability_block_reason(

        self,

        descriptor,

        capabilities,

    ):

        if descriptor.capability is None:

            return None

        if (

            self._capability_supported(

                capabilities,

                descriptor.capability,
            )
        ):

            return None

        return (

            f"{descriptor.label} is not "
            "supported by this workspace."
        )

    def _readiness_block_reason(

        self,

        descriptor,

        readiness,

    ):

        if (

            descriptor.action

            in _DIAGNOSTIC_ACTIONS
        ):

            return None

        if (

            readiness.status

            == ResearchWorkspaceReadinessStatus
            .UNAVAILABLE
        ):

            return (
                "The workspace is currently "
                "unavailable."
            )

        return None

    def _evaluate_workspace_action(

        self,

        descriptor,

        capabilities,

        readiness,

    ):

        reason = (

            self._capability_block_reason(

                descriptor,

                capabilities,
            )

            or self._readiness_block_reason(

                descriptor,

                readiness,
            )
        )

        return (

            ResearchWorkspaceActionAvailability(

                action=(
                    descriptor.action
                ),

                available=(
                    reason is None
                ),

                reason=reason,

                descriptor=descriptor,
            )
        )

    def _evaluate_session_action(

        self,

        descriptor,

        capabilities,

        readiness,

        status,

        archived,

    ):

        reason = (

            self._capability_block_reason(

                descriptor,

                capabilities,
            )

            or self._readiness_block_reason(

                descriptor,

                readiness,
            )

            or self._session_state_block_reason(

                descriptor.action,

                status,

                archived,
            )
        )

        return (

            ResearchWorkspaceActionAvailability(

                action=(
                    descriptor.action
                ),

                available=(
                    reason is None
                ),

                reason=reason,

                descriptor=descriptor,
            )
        )

    @staticmethod
    def _session_state_block_reason(

        action,

        status,

        archived,

    ):

        if (

            action

            == ResearchWorkspaceAction
            .PAUSE_SESSION

            and status

            != ResearchSessionStatus
            .ACTIVE
        ):

            return (
                "The session is not "
                "currently active."
            )

        if (

            action

            == ResearchWorkspaceAction
            .RESUME_SESSION

            and status

            != ResearchSessionStatus
            .PAUSED
        ):

            return (
                "The session is not "
                "currently paused."
            )

        if (

            action

            == ResearchWorkspaceAction
            .COMPLETE_SESSION

            and status

            == ResearchSessionStatus
            .COMPLETED
        ):

            return (
                "The session is already "
                "completed."
            )

        if (

            action

            == ResearchWorkspaceAction
            .ARCHIVE_SESSION

            and archived
        ):

            return (
                "The session is already "
                "archived."
            )

        if (

            action

            == ResearchWorkspaceAction
            .RESTORE_SESSION

            and not archived
        ):

            return (
                "The session is not "
                "archived."
            )

        return None

    @staticmethod
    def _build_projection(

        scope,

        entity_id,

        availabilities,

        include_unavailable,

        mutating_only,

    ):

        if mutating_only:

            availabilities = [

                item

                for item

                in availabilities

                if (

                    item.descriptor
                    .mutating
                )
            ]

        if not include_unavailable:

            availabilities = [

                item

                for item

                in availabilities

                if item.available
            ]

        return (

            ResearchWorkspaceActionProjection(

                scope=scope,

                entity_id=entity_id,

                actions=availabilities,

                available_count=(

                    sum(

                        1

                        for item

                        in availabilities

                        if item.available
                    )
                ),

                unavailable_count=(

                    sum(

                        1

                        for item

                        in availabilities

                        if not item.available
                    )
                ),
            )
        )
