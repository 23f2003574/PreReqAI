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

    def get_capabilities(self):

        if (

            self._capabilities

            is _UNRESOLVED
        ):

            self._capabilities = (

                self._capability_registry
                .list_capabilities()
            )

        return self._capabilities

    def get_readiness(self):

        if (

            self._readiness

            is _UNRESOLVED
        ):

            self._readiness = (

                self._readiness_assessor
                .assess()
            )

        return self._readiness

    def get_integrity_report(self):

        if (

            self._integrity_report

            is _UNRESOLVED
        ):

            self._integrity_report = (

                self._integrity_auditor
                .audit()
            )

        return self._integrity_report

    def get_workspace_insights(self):

        if (

            self._workspace_insights

            is _UNRESOLVED
        ):

            self._workspace_insights = (

                self._insights_service
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

                self._session_manager
                .load_session(
                    session_id
                )
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

                self._profile_store
                .get(
                    session_id
                )
            )

        return (

            self._profiles_by_id[
                session_id
            ]
        )
