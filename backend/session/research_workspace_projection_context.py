from .research_workspace_consumer_projection_diagnostic_failure import (
    ResearchWorkspaceConsumerProjectionDiagnosticFailure,
)

from .research_workspace_consumer_projection_diagnostic_status import (
    ResearchWorkspaceConsumerProjectionDiagnosticStatus,
)

from .research_workspace_monotonic_clock import (
    ResearchWorkspaceMonotonicClock,
)


_UNRESOLVED = object()


class ResearchWorkspaceProjectionContext:
    """
    Lazily resolves and reuses shared
    read state for the projections
    participating in one logical
    workspace read operation.
    """

    def __init__(

        self,

        *,

        capability_registry,

        readiness_assessor,

        integrity_auditor,

        insights_service,

        session_manager,

        profile_store,

        insights_dormant_session_limit=50,

        insights_dormant_after_days=30,

        clock=None,

        diagnostics=None,

    ):

        self._capability_registry = (
            capability_registry
        )

        self._readiness_assessor = (
            readiness_assessor
        )

        self._integrity_auditor = (
            integrity_auditor
        )

        self._insights_service = (
            insights_service
        )

        self._session_manager = (
            session_manager
        )

        self._profile_store = (
            profile_store
        )

        self._insights_dormant_session_limit = (
            insights_dormant_session_limit
        )

        self._insights_dormant_after_days = (
            insights_dormant_after_days
        )

        self._clock = (

            clock

            or ResearchWorkspaceMonotonicClock()
        )

        self._diagnostics = (
            diagnostics
        )

        self._capabilities = (
            _UNRESOLVED
        )

        self._readiness = (
            _UNRESOLVED
        )

        self._integrity_report = (
            _UNRESOLVED
        )

        self._workspace_insights = (
            _UNRESOLVED
        )

        self._sessions_by_id = {}

        self._profiles_by_id = {}

    def _record_and_resolve(

        self,

        name,

        resolver,

        key=None,

    ):

        if self._diagnostics is None:

            return resolver()

        started_at = (
            self._clock.now()
        )

        try:

            value = resolver()

        except Exception as error:

            duration_seconds = (

                self._clock.now()

                - started_at
            )

            self._diagnostics.record_input_resolution(

                name=name,

                key=key,

                duration_seconds=(
                    duration_seconds
                ),

                status=(

                    ResearchWorkspaceConsumerProjectionDiagnosticStatus
                    .FAILED
                ),

                failure=(

                    ResearchWorkspaceConsumerProjectionDiagnosticFailure(

                        error_type=(

                            type(
                                error
                            ).__name__
                        ),
                    )
                ),
            )

            raise

        duration_seconds = (

            self._clock.now()

            - started_at
        )

        self._diagnostics.record_input_resolution(

            name=name,

            key=key,

            duration_seconds=(
                duration_seconds
            ),

            status=(

                ResearchWorkspaceConsumerProjectionDiagnosticStatus
                .SUCCEEDED
            ),
        )

        return value

    def _record_reuse(

        self,

        name,

        key=None,

    ):

        if self._diagnostics is not None:

            self._diagnostics.record_input_reuse(

                name=name,

                key=key,
            )

    def get_capabilities(self):

        if (

            self._capabilities

            is _UNRESOLVED
        ):

            self._capabilities = (

                self._record_and_resolve(

                    "workspace.capabilities",

                    self._capability_registry
                    .list_capabilities,
                )
            )

        else:

            self._record_reuse(
                "workspace.capabilities"
            )

        return self._capabilities

    def get_readiness(self):

        if (

            self._readiness

            is _UNRESOLVED
        ):

            self._readiness = (

                self._record_and_resolve(

                    "workspace.readiness",

                    self._readiness_assessor
                    .assess,
                )
            )

        else:

            self._record_reuse(
                "workspace.readiness"
            )

        return self._readiness

    def get_integrity_report(self):

        if (

            self._integrity_report

            is _UNRESOLVED
        ):

            self._integrity_report = (

                self._record_and_resolve(

                    "workspace.integrity",

                    self._integrity_auditor
                    .audit,
                )
            )

        else:

            self._record_reuse(
                "workspace.integrity"
            )

        return self._integrity_report

    def get_workspace_insights(self):

        if (

            self._workspace_insights

            is _UNRESOLVED
        ):

            self._workspace_insights = (

                self._record_and_resolve(

                    "workspace.insights",

                    lambda: (

                        self
                        ._insights_service
                        .build_insights(

                            top_tag_limit=0,

                            collection_limit=0,

                            recent_session_limit=0,

                            dormant_session_limit=(

                                self
                                ._insights_dormant_session_limit
                            ),

                            dormant_after_days=(

                                self
                                ._insights_dormant_after_days
                            ),
                        )
                    ),
                )
            )

        else:

            self._record_reuse(
                "workspace.insights"
            )

        return self._workspace_insights

    def get_session(

        self,

        session_id,

    ):

        if (

            session_id

            not in self._sessions_by_id
        ):

            self._sessions_by_id[
                session_id
            ] = (

                self._record_and_resolve(

                    "session",

                    lambda: (

                        self
                        ._session_manager
                        .load_session(
                            session_id
                        )
                    ),

                    key=session_id,
                )
            )

        else:

            self._record_reuse(

                "session",

                key=session_id,
            )

        return (

            self._sessions_by_id[
                session_id
            ]
        )

    def get_session_profile(

        self,

        session_id,

    ):

        if (

            session_id

            not in self._profiles_by_id
        ):

            self._profiles_by_id[
                session_id
            ] = (

                self._record_and_resolve(

                    "session_profile",

                    lambda: (

                        self
                        ._profile_store
                        .get(
                            session_id
                        )
                    ),

                    key=session_id,
                )
            )

        else:

            self._record_reuse(

                "session_profile",

                key=session_id,
            )

        return (

            self._profiles_by_id[
                session_id
            ]
        )
