from .research_workspace_consumer_projection_diagnostic_failure import (
    ResearchWorkspaceConsumerProjectionDiagnosticFailure,
)

from .research_workspace_consumer_projection_diagnostic_status import (
    ResearchWorkspaceConsumerProjectionDiagnosticStatus,
)

from .research_workspace_consumer_projection_unusable_freshness_error import (
    ResearchWorkspaceConsumerProjectionUnusableFreshnessError,
)

from .research_workspace_consumer_projection_freshness_status import (
    ResearchWorkspaceConsumerProjectionFreshnessStatus,
)

from .research_workspace_monotonic_clock import (
    ResearchWorkspaceMonotonicClock,
)

from .research_workspace_utc_clock import (
    ResearchWorkspaceUtcClock,
)


_UNRESOLVED = object()

_RECENT_ACTIVITY_FRESHNESS_SOURCE = (
    "workspace.recent_activity"
)


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

        activity_service=None,

        freshness_evaluator=None,

        utc_clock=None,

        observed_at=None,

        provenance=None,

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

        self._activity_service = (
            activity_service
        )

        self._freshness_evaluator = (
            freshness_evaluator
        )

        self._utc_clock = (

            utc_clock

            or ResearchWorkspaceUtcClock()
        )

        self._observed_at = (

            observed_at

            or self._utc_clock.now()
        )

        self._provenance = (
            provenance
        )

        self._recent_activity_freshness = (
            _UNRESOLVED
        )

        self._recent_activity_freshness_error = (
            None
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

    @property
    def observed_at(self):

        return self._observed_at

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

    def _register_source_provenance(

        self,

        source_name,

        *,

        source_timestamp=None,

        freshness_status=None,

    ):

        if self._provenance is None:

            return None

        return (

            self._provenance
            .register_source(

                source_name=(
                    source_name
                ),

                source_timestamp=(
                    source_timestamp
                ),

                freshness_status=(
                    freshness_status
                ),
            )
        )

    def get_source_provenance_node_id(

        self,

        source_name,

    ):
        """
        Returns the request-scoped
        provenance node ID for a named
        source, registering it (with no
        timestamp/freshness metadata) if
        it has not already been resolved
        through this context. Idempotent
        — safe to call from projectors
        building derivation edges without
        needing the context to track a
        separate provenance identity per
        getter.
        """

        return (

            self._register_source_provenance(
                source_name
            )
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

            self._register_source_provenance(
                "workspace.capabilities"
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

            self._register_source_provenance(
                "workspace.readiness"
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

            self._register_source_provenance(
                "workspace.integrity"
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

            self._register_source_provenance(
                "workspace.insights"
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

    def get_recent_activity_freshness(self):
        """
        Evaluates how current the most
        recent workspace activity event
        is. Returns None if freshness
        evaluation is not configured or
        no activity exists yet — neither
        case is a freshness rejection.
        Raises
        ResearchWorkspaceConsumerProjectionUnusableFreshnessError
        if the latest activity is too old
        under policy; that rejection is
        memoized and re-raised on later
        calls within the same operation
        rather than re-evaluated.
        """

        if (

            self._recent_activity_freshness

            is _UNRESOLVED
        ):

            evaluation = (

                self._record_and_resolve(

                    _RECENT_ACTIVITY_FRESHNESS_SOURCE,

                    self._evaluate_recent_activity_freshness,
                )
            )

            if self._diagnostics is not None:

                self._diagnostics.record_input_freshness(

                    name=(
                        _RECENT_ACTIVITY_FRESHNESS_SOURCE
                    ),

                    freshness=evaluation,
                )

            if (

                evaluation is not None

                and evaluation.status

                == ResearchWorkspaceConsumerProjectionFreshnessStatus
                .UNUSABLE
            ):

                self._recent_activity_freshness_error = (

                    ResearchWorkspaceConsumerProjectionUnusableFreshnessError(

                        source_name=(
                            _RECENT_ACTIVITY_FRESHNESS_SOURCE
                        ),

                        evaluation=(
                            evaluation
                        ),
                    )
                )

            if evaluation is not None:

                self._register_source_provenance(

                    _RECENT_ACTIVITY_FRESHNESS_SOURCE,

                    source_timestamp=(
                        evaluation
                        .source_timestamp
                    ),

                    freshness_status=(
                        evaluation.status
                    ),
                )

            else:

                self._register_source_provenance(
                    _RECENT_ACTIVITY_FRESHNESS_SOURCE
                )

            self._recent_activity_freshness = (
                evaluation
            )

        else:

            self._record_reuse(
                _RECENT_ACTIVITY_FRESHNESS_SOURCE
            )

        if (

            self._recent_activity_freshness_error

            is not None
        ):

            raise (
                self._recent_activity_freshness_error
            )

        return (
            self._recent_activity_freshness
        )

    def _evaluate_recent_activity_freshness(self):

        if (

            self._activity_service is None

            or self._freshness_evaluator

            is None
        ):

            return None

        page = (

            self._activity_service
            .recent_activity(

                page=1,

                page_size=1,
            )
        )

        if not page.items:

            return None

        latest_timestamp = (

            page.items[0]
            .occurred_at
        )

        return (

            self._freshness_evaluator
            .evaluate(

                source_name=(
                    _RECENT_ACTIVITY_FRESHNESS_SOURCE
                ),

                source_timestamp=(
                    latest_timestamp
                ),

                evaluated_at=(
                    self._observed_at
                ),
            )
        )
