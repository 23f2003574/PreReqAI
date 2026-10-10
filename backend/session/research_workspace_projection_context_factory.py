from .research_workspace_projection_context import (
    ResearchWorkspaceProjectionContext,
)


class ResearchWorkspaceProjectionContextFactory:
    """
    Application-scoped factory that
    creates a fresh, request-scoped
    projection context for each logical
    workspace read operation.
    """

    def __init__(

        self,

        capability_registry,

        readiness_assessor,

        integrity_auditor,

        insights_service,

        session_manager,

        profile_store,

        insights_dormant_session_limit=50,

        insights_dormant_after_days=30,

        clock=None,

        activity_service=None,

        freshness_evaluator=None,

        utc_clock=None,

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

        self._clock = clock

        self._activity_service = (
            activity_service
        )

        self._freshness_evaluator = (
            freshness_evaluator
        )

        self._utc_clock = utc_clock

    def create(

        self,

        *,

        diagnostics=None,

        provenance=None,

    ):

        return (

            ResearchWorkspaceProjectionContext(

                capability_registry=(

                    self
                    ._capability_registry
                ),

                readiness_assessor=(

                    self
                    ._readiness_assessor
                ),

                integrity_auditor=(

                    self
                    ._integrity_auditor
                ),

                insights_service=(

                    self
                    ._insights_service
                ),

                session_manager=(

                    self
                    ._session_manager
                ),

                profile_store=(

                    self
                    ._profile_store
                ),

                insights_dormant_session_limit=(

                    self
                    ._insights_dormant_session_limit
                ),

                insights_dormant_after_days=(

                    self
                    ._insights_dormant_after_days
                ),

                clock=self._clock,

                diagnostics=diagnostics,

                activity_service=(

                    self
                    ._activity_service
                ),

                freshness_evaluator=(

                    self
                    ._freshness_evaluator
                ),

                utc_clock=self._utc_clock,

                provenance=provenance,
            )
        )
