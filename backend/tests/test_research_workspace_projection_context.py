from types import (
    SimpleNamespace,
)

import pytest

from backend.session import (
    ResearchIntegrityReport,
    ResearchWorkspaceActionCatalog,
    ResearchWorkspaceActionProjector,
    ResearchWorkspaceAttentionProjector,
    ResearchWorkspaceBootstrapProjector,
    ResearchWorkspaceProjectionContext,
    ResearchWorkspaceReadinessAssessment,
    ResearchWorkspaceReadinessStatus,
)

from frontend.src.app import (
    PreReqAIApplication,
)


class CountingCapabilityRegistry:

    def __init__(

        self,

        capabilities=(),

    ):

        self._capabilities = list(
            capabilities
        )

        self.calls = 0

    def list_capabilities(self):

        self.calls += 1

        return list(
            self._capabilities
        )


class CountingReadinessAssessor:

    def __init__(

        self,

        results,

    ):

        self._results = list(
            results
        )

        self.calls = 0

    def assess(self):

        index = min(

            self.calls,

            len(
                self._results
            )

            - 1,
        )

        self.calls += 1

        return self._results[
            index
        ]


class CountingIntegrityAuditor:

    def __init__(

        self,

        report=None,

    ):

        self._report = (

            report

            or ResearchIntegrityReport()
        )

        self.calls = 0

    def audit(self):

        self.calls += 1

        return self._report


class BrokenIntegrityAuditor:

    def audit(self):

        raise RuntimeError(
            "integrity auditor unavailable"
        )


class CountingInsightsService:

    def __init__(

        self,

        insights=None,

    ):

        self._insights = (

            insights

            or SimpleNamespace(

                overview=None,

                dormant_sessions=[],
            )
        )

        self.calls = 0

    def build_insights(

        self,

        **kwargs,

    ):

        self.calls += 1

        return self._insights


class CountingSessionManager:

    def __init__(

        self,

        sessions,

    ):

        self._sessions = dict(
            sessions
        )

        self.calls_by_id = {}

    def load_session(

        self,

        session_id,

    ):

        self.calls_by_id[
            session_id
        ] = (

            self.calls_by_id.get(

                session_id,

                0,
            )

            + 1
        )

        return self._sessions.get(
            session_id
        )


class CountingProfileStore:

    def __init__(self):

        self.calls_by_id = {}

    def get(

        self,

        session_id,

    ):

        self.calls_by_id[
            session_id
        ] = (

            self.calls_by_id.get(

                session_id,

                0,
            )

            + 1
        )

        return None


class FakeContextFactory:

    def __init__(

        self,

        context,

    ):

        self._context = context

    def create(

        self,

        *,

        diagnostics=None,

    ):

        return self._context


def make_context(

    capability_registry=None,

    readiness_assessor=None,

    integrity_auditor=None,

    insights_service=None,

    session_manager=None,

    profile_store=None,

):

    return (

        ResearchWorkspaceProjectionContext(

            capability_registry=(

                capability_registry

                or CountingCapabilityRegistry()
            ),

            readiness_assessor=(

                readiness_assessor

                or CountingReadinessAssessor(
                    [None]
                )
            ),

            integrity_auditor=(

                integrity_auditor

                or CountingIntegrityAuditor()
            ),

            insights_service=(

                insights_service

                or CountingInsightsService()
            ),

            session_manager=(

                session_manager

                or CountingSessionManager({})
            ),

            profile_store=(

                profile_store

                or CountingProfileStore()
            ),
        )
    )


def test_capabilities_resolve_lazily():

    registry = (
        CountingCapabilityRegistry()
    )

    context = make_context(
        capability_registry=registry,
    )

    assert registry.calls == 0

    context.get_capabilities()

    assert registry.calls == 1


def test_capabilities_resolve_only_once():

    registry = (

        CountingCapabilityRegistry(
            [
                "sessions",
            ],
        )
    )

    context = make_context(
        capability_registry=registry,
    )

    first = context.get_capabilities()

    second = context.get_capabilities()

    third = context.get_capabilities()

    assert registry.calls == 1

    assert first is second is third


def test_readiness_resolves_only_once():

    assessor = (

        CountingReadinessAssessor(
            ["ready"],
        )
    )

    context = make_context(
        readiness_assessor=assessor,
    )

    context.get_readiness()

    context.get_readiness()

    context.get_readiness()

    assert assessor.calls == 1


def test_integrity_report_resolves_only_once():

    auditor = (
        CountingIntegrityAuditor()
    )

    context = make_context(
        integrity_auditor=auditor,
    )

    context.get_integrity_report()

    context.get_integrity_report()

    assert auditor.calls == 1


def test_workspace_insights_resolve_only_once():

    insights_service = (
        CountingInsightsService()
    )

    context = make_context(
        insights_service=insights_service,
    )

    context.get_workspace_insights()

    context.get_workspace_insights()

    context.get_workspace_insights()

    assert insights_service.calls == 1


def test_sessions_are_cached_per_id():

    session_manager = (

        CountingSessionManager(
            {
                "session-1": object(),

                "session-2": object(),
            }
        )
    )

    context = make_context(
        session_manager=session_manager,
    )

    context.get_session(
        "session-1"
    )

    context.get_session(
        "session-1"
    )

    context.get_session(
        "session-2"
    )

    context.get_session(
        "session-1"
    )

    assert (
        session_manager.calls_by_id[
            "session-1"
        ]

        == 1
    )

    assert (
        session_manager.calls_by_id[
            "session-2"
        ]

        == 1
    )


def test_different_contexts_do_not_share_resolved_state():

    assessor = (

        CountingReadinessAssessor(
            [
                "ready",

                "degraded",
            ],
        )
    )

    context_a = make_context(
        readiness_assessor=assessor,
    )

    context_b = make_context(
        readiness_assessor=assessor,
    )

    first = context_a.get_readiness()

    second = context_b.get_readiness()

    assert assessor.calls == 2

    assert first != second


def test_unused_resolvers_are_never_called():

    capability_registry = (
        CountingCapabilityRegistry()
    )

    readiness_assessor = (

        CountingReadinessAssessor(
            [None]
        )
    )

    integrity_auditor = (
        CountingIntegrityAuditor()
    )

    insights_service = (
        CountingInsightsService()
    )

    session_manager = (
        CountingSessionManager({})
    )

    context = make_context(
        capability_registry=(
            capability_registry
        ),

        readiness_assessor=(
            readiness_assessor
        ),

        integrity_auditor=(
            integrity_auditor
        ),

        insights_service=(
            insights_service
        ),

        session_manager=(
            session_manager
        ),
    )

    context.get_capabilities()

    assert readiness_assessor.calls == 0

    assert integrity_auditor.calls == 0

    assert insights_service.calls == 0

    assert session_manager.calls_by_id == {}


def test_same_context_preserves_resolved_readiness():

    assessor = (

        CountingReadinessAssessor(
            [
                "ready",

                "degraded",
            ],
        )
    )

    context = make_context(
        readiness_assessor=assessor,
    )

    first = context.get_readiness()

    second = context.get_readiness()

    assert first == "ready"

    assert second == "ready"

    assert assessor.calls == 1


def test_new_context_observes_fresh_readiness():

    assessor = (

        CountingReadinessAssessor(
            [
                "ready",

                "degraded",
            ],
        )
    )

    context_a = make_context(
        readiness_assessor=assessor,
    )

    context_b = make_context(
        readiness_assessor=assessor,
    )

    assert (
        context_a.get_readiness()

        == "ready"
    )

    assert (
        context_b.get_readiness()

        == "degraded"
    )


def test_resolver_failure_is_not_silently_converted():

    context = make_context(
        integrity_auditor=(
            BrokenIntegrityAuditor()
        ),
    )

    with pytest.raises(
        RuntimeError,
    ):

        context.get_integrity_report()


def test_resolver_failure_leaves_value_unresolved_for_retry():

    calls = {

        "count": 0,
    }

    class FlakyIntegrityAuditor:

        def audit(self):

            calls[
                "count"
            ] += 1

            if calls[
                "count"
            ] == 1:

                raise RuntimeError(
                    "temporary failure"
                )

            return (
                ResearchIntegrityReport()
            )

    context = make_context(
        integrity_auditor=(
            FlakyIntegrityAuditor()
        ),
    )

    with pytest.raises(
        RuntimeError,
    ):

        context.get_integrity_report()

    report = (
        context.get_integrity_report()
    )

    assert isinstance(
        report,

        ResearchIntegrityReport,
    )

    assert calls[
        "count"
    ] == 2


def test_context_is_read_only():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(
        "session-a"
    )

    application.save_research_session(
        "session-a"
    )

    before_session_count = len(

        application
        .session_manager
        .list_sessions()
    )

    before_sequence = (

        application
        .research_workspace_change_feed
        .latest_sequence
    )

    context = (

        application
        .research_workspace_projection_context_factory
        .create()
    )

    context.get_capabilities()

    context.get_readiness()

    context.get_integrity_report()

    context.get_workspace_insights()

    context.get_session(
        "session-a"
    )

    context.get_session_profile(
        "session-a"
    )

    after_session_count = len(

        application
        .session_manager
        .list_sessions()
    )

    after_sequence = (

        application
        .research_workspace_change_feed
        .latest_sequence
    )

    assert (
        before_session_count

        == after_session_count
    )

    assert before_sequence == after_sequence


def test_bootstrap_shares_readiness_with_attention():

    application = (
        PreReqAIApplication()
    )

    original_assess = (

        application
        .research_workspace_readiness_assessor
        .assess
    )

    calls = {
        "count": 0,
    }

    def counting_assess():

        calls[
            "count"
        ] += 1

        return original_assess()

    application.research_workspace_readiness_assessor.assess = (
        counting_assess
    )

    application.research_workspace.get_bootstrap()

    assert calls[
        "count"
    ] == 1


def test_bootstrap_shares_readiness_with_action_discovery():

    application = (
        PreReqAIApplication()
    )

    original_assess = (

        application
        .research_workspace_readiness_assessor
        .assess
    )

    calls = {
        "count": 0,
    }

    def counting_assess():

        calls[
            "count"
        ] += 1

        return original_assess()

    application.research_workspace_readiness_assessor.assess = (
        counting_assess
    )

    projection = (

        application
        .research_workspace
        .get_bootstrap()
    )

    assert calls[
        "count"
    ] == 1

    assert len(
        projection.workspace_actions
    ) > 0


def test_bootstrap_shares_capabilities_with_action_discovery():

    registry = (

        CountingCapabilityRegistry(
            [],
        )
    )

    ready_assessment = (

        ResearchWorkspaceReadinessAssessment(

            status=(

                ResearchWorkspaceReadinessStatus
                .READY
            ),

            ready=True,

            blocking=False,

            checks=[],

            warnings=[],

            blocking_reasons=[],
        )
    )

    readiness_assessor = (

        CountingReadinessAssessor(
            [
                ready_assessment,
            ],
        )
    )

    context = make_context(
        capability_registry=registry,

        readiness_assessor=readiness_assessor,
    )

    context_factory = (

        FakeContextFactory(
            context
        )
    )

    action_catalog = (
        ResearchWorkspaceActionCatalog()
    )

    action_projector = (

        ResearchWorkspaceActionProjector(

            action_catalog=(
                action_catalog
            ),

            context_factory=(
                context_factory
            ),
        )
    )

    context.get_capabilities()

    action_projector.project_workspace_actions(
        context=context,
    )

    assert registry.calls == 1


def test_optional_projection_failure_remains_projector_responsibility():

    ready_assessment = (

        ResearchWorkspaceReadinessAssessment(

            status=(

                ResearchWorkspaceReadinessStatus
                .READY
            ),

            ready=True,

            blocking=False,

            checks=[],

            warnings=[],

            blocking_reasons=[],
        )
    )

    context = make_context(
        integrity_auditor=(
            BrokenIntegrityAuditor()
        ),

        readiness_assessor=(

            CountingReadinessAssessor(
                [
                    ready_assessment,
                ]
            )
        ),
    )

    context_factory = (

        FakeContextFactory(
            context
        )
    )

    attention_projector = (

        ResearchWorkspaceAttentionProjector(
            context_factory=(
                context_factory
            ),
        )
    )

    action_catalog = (
        ResearchWorkspaceActionCatalog()
    )

    action_projector = (

        ResearchWorkspaceActionProjector(

            action_catalog=(
                action_catalog
            ),

            context_factory=(
                context_factory
            ),
        )
    )

    with pytest.raises(
        RuntimeError,
    ):

        attention_projector.project(
            context=context,
        )

    bootstrap_projector = (

        ResearchWorkspaceBootstrapProjector(

            context_factory=(
                context_factory
            ),

            discovery_service=None,

            activity_service=None,

            attention_projector=(
                attention_projector
            ),

            action_projector=(
                action_projector
            ),
        )
    )

    projection = (

        bootstrap_projector.project(
            context=context,

            recent_session_limit=0,

            recent_activity_limit=0,
        )
    )

    assert (

        "Attention summary could "
        "not be computed."

        in projection.warnings
    )

    assert (
        projection.attention.total_count

        == 0
    )


def test_gateway_creates_fresh_contexts_per_composite_operation():

    application = (
        PreReqAIApplication()
    )

    original_create = (

        application
        .research_workspace_projection_context_factory
        .create
    )

    created_contexts = []

    def counting_create():

        context = original_create()

        created_contexts.append(
            context
        )

        return context

    application.research_workspace_projection_context_factory.create = (
        counting_create
    )

    application.research_workspace.get_bootstrap()

    application.research_workspace.get_bootstrap()

    assert len(
        created_contexts
    ) == 2

    assert (

        created_contexts[0]

        is not created_contexts[1]
    )


def test_action_projection_uses_context_session_resolution():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(
        "session-a"
    )

    application.save_research_session(
        "session-a"
    )

    application.update_research_session_profile(
        "session-a",

        display_name="Session A",
    )

    context = (

        application
        .research_workspace_projection_context_factory
        .create()
    )

    original_load_session = (

        application
        .session_manager
        .load_session
    )

    calls = {
        "count": 0,
    }

    def counting_load_session(
        session_id,
    ):

        calls[
            "count"
        ] += 1

        return original_load_session(
            session_id
        )

    application.session_manager.load_session = (
        counting_load_session
    )

    application.research_workspace_action_projector.project_session_actions(
        "session-a",

        context=context,
    )

    application.research_workspace_action_projector.project_session_actions(
        "session-a",

        context=context,
    )

    assert calls[
        "count"
    ] == 1


def test_existing_public_projection_behavior_remains_compatible():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(
        "session-a"
    )

    application.save_research_session(
        "session-a"
    )

    bootstrap = (

        application
        .research_workspace
        .get_bootstrap()
    )

    attention = (

        application
        .research_workspace
        .get_attention()
    )

    actions = (

        application
        .research_workspace
        .list_workspace_actions()
    )

    assert bootstrap.readiness is not None

    assert attention.total_count >= 0

    assert actions.available_count >= 0
