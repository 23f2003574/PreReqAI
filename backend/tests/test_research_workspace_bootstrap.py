from backend.session import (
    ResearchWorkspaceBootstrapProjector,
    ResearchWorkspaceProjectionContext,
    ResearchWorkspaceReadinessStatus,
)

from frontend.src.app import (
    PreReqAIApplication,
)


class FakeCapabilityRegistry:

    def __init__(

        self,

        capabilities,

    ):

        self._capabilities = (
            capabilities
        )

    def list_capabilities(self):

        return list(
            self._capabilities
        )

    def supports(

        self,

        capability,

    ):

        return True


class FakeReadinessAssessor:

    def __init__(

        self,

        assessment,

    ):

        self.assessment = (
            assessment
        )

    def assess(self):

        return self.assessment


class BrokenActivityService:

    def recent_activity(

        self,

        page=1,

        page_size=50,

    ):

        raise RuntimeError(
            "activity timeline unavailable"
        )


def populate_sessions(

    application,

    count,

):

    for index in range(count):

        session_id = (
            f"session-{index}"
        )

        application.activate_research_session(
            session_id
        )

        application.save_research_session(

            session_id,

            paper_title=(
                f"Paper {index}"
            ),
        )

        application.update_research_session_profile(

            session_id,

            display_name=(
                f"Session {index}"
            ),
        )


class FakeContextFactory:

    def __init__(

        self,

        capability_registry,

        readiness_assessor,

        integrity_auditor,

        insights_service,

        session_manager,

        profile_store,

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

    def create(self):

        return (

            ResearchWorkspaceProjectionContext(

                capability_registry=(

                    self._capability_registry
                ),

                readiness_assessor=(

                    self._readiness_assessor
                ),

                integrity_auditor=(

                    self._integrity_auditor
                ),

                insights_service=(

                    self._insights_service
                ),

                session_manager=(

                    self._session_manager
                ),

                profile_store=(

                    self._profile_store
                ),
            )
        )


def create_bootstrap_projector(

    application,

    capability_registry=None,

    readiness_assessor=None,

    insights_service=None,

    discovery_service=None,

    activity_service=None,

    attention_projector=None,

    action_projector=None,

):

    context_factory = (

        FakeContextFactory(

            capability_registry=(

                capability_registry

                or (

                    application
                    .research_workspace_capabilities
                )
            ),

            readiness_assessor=(

                readiness_assessor

                or (

                    application
                    .research_workspace_readiness_assessor
                )
            ),

            integrity_auditor=(

                application
                .research_workspace_integrity_auditor
            ),

            insights_service=(

                insights_service

                or (

                    application
                    .research_workspace_insights_service
                )
            ),

            session_manager=(
                application.session_manager
            ),

            profile_store=(
                application.session_profile_store
            ),
        )
    )

    return (

        ResearchWorkspaceBootstrapProjector(

            context_factory=(
                context_factory
            ),

            discovery_service=(

                discovery_service

                or application.session_query_service
            ),

            activity_service=(

                activity_service

                or application.research_activity_service
            ),

            attention_projector=(

                attention_projector

                or (

                    application
                    .research_workspace_attention_projector
                )
            ),

            action_projector=(

                action_projector

                or (

                    application
                    .research_workspace_action_projector
                )
            ),
        )
    )


def test_healthy_workspace_produces_complete_bootstrap_projection():

    application = (
        PreReqAIApplication()
    )

    populate_sessions(
        application,
        2,
    )

    projection = (

        application
        .research_workspace
        .get_bootstrap()
    )

    assert len(
        projection.capabilities
    ) == len(

        application
        .research_workspace_capabilities
        .list_capabilities()
    )

    assert (

        projection.readiness.status

        == ResearchWorkspaceReadinessStatus
        .READY
    )

    assert (
        projection.overview
        .total_sessions

        == 2
    )

    assert len(
        projection.recent_sessions
    ) == 2

    assert len(
        projection.recent_activity
    ) > 0

    assert projection.warnings == []


def test_capability_data_comes_from_registry():

    application = (
        PreReqAIApplication()
    )

    known_capabilities = (

        application
        .research_workspace_capabilities
        .list_capabilities()
    )

    fake_registry = (

        FakeCapabilityRegistry(
            known_capabilities
        )
    )

    projector = (

        create_bootstrap_projector(

            application,

            capability_registry=(
                fake_registry
            ),
        )
    )

    projection = projector.project()

    assert (

        projection.capabilities

        == known_capabilities
    )


def test_readiness_comes_from_readiness_assessor():

    application = (
        PreReqAIApplication()
    )

    from backend.session import (
        ResearchWorkspaceReadinessAssessment,
    )

    canned_assessment = (

        ResearchWorkspaceReadinessAssessment(

            status=(

                ResearchWorkspaceReadinessStatus
                .DEGRADED
            ),

            ready=True,

            blocking=False,

            checks=[],

            warnings=[
                "Reactive synchronization "
                "is unavailable."
            ],

            blocking_reasons=[],
        )
    )

    projector = (

        create_bootstrap_projector(

            application,

            readiness_assessor=(

                FakeReadinessAssessor(
                    canned_assessment
                )
            ),
        )
    )

    projection = projector.project()

    assert (
        projection.readiness

        is canned_assessment
    )

    assert (

        projection.readiness.status

        == ResearchWorkspaceReadinessStatus
        .DEGRADED
    )

    assert projection.readiness.ready is True

    assert (
        projection.readiness.blocking

        is False
    )


def test_recent_session_limit_is_respected():

    application = (
        PreReqAIApplication()
    )

    populate_sessions(
        application,
        6,
    )

    original_query = (

        application
        .session_query_service
        .query
    )

    captured_queries = []

    def spy_query(query):

        captured_queries.append(
            query
        )

        return original_query(
            query
        )

    application.session_query_service.query = (
        spy_query
    )

    projector = (

        create_bootstrap_projector(
            application
        )
    )

    projection = projector.project(

        recent_session_limit=3,
    )

    assert len(
        projection.recent_sessions
    ) == 3

    assert (
        captured_queries[-1].limit

        == 3
    )


def test_recent_activity_limit_is_respected():

    application = (
        PreReqAIApplication()
    )

    populate_sessions(
        application,
        6,
    )

    original_recent_activity = (

        application
        .research_activity_service
        .recent_activity
    )

    captured_page_sizes = []

    def spy_recent_activity(

        page=1,

        page_size=50,

    ):

        captured_page_sizes.append(
            page_size
        )

        return original_recent_activity(

            page=page,

            page_size=page_size,
        )

    application.research_activity_service.recent_activity = (
        spy_recent_activity
    )

    projector = (

        create_bootstrap_projector(
            application
        )
    )

    projection = projector.project(

        recent_activity_limit=2,
    )

    assert len(
        projection.recent_activity
    ) == 2

    assert (
        captured_page_sizes[-1]

        == 2
    )


def test_empty_workspace_is_valid():

    application = (
        PreReqAIApplication()
    )

    projection = (

        application
        .research_workspace
        .get_bootstrap()
    )

    assert (

        projection.readiness.status

        == ResearchWorkspaceReadinessStatus
        .READY
    )

    assert projection.recent_sessions == []

    assert projection.recent_activity == []

    assert projection.warnings == []


def test_optional_activity_failure_is_isolated():

    application = (
        PreReqAIApplication()
    )

    populate_sessions(
        application,
        2,
    )

    projector = (

        create_bootstrap_projector(

            application,

            activity_service=(
                BrokenActivityService()
            ),
        )
    )

    projection = projector.project()

    assert projection.recent_activity == []

    assert (

        "Recent activity could not "
        "be loaded."

        in projection.warnings
    )

    assert len(
        projection.capabilities
    ) > 0

    assert (

        projection.readiness.status

        == ResearchWorkspaceReadinessStatus
        .READY
    )

    assert len(
        projection.recent_sessions
    ) == 2


def test_invalid_limits_are_rejected():

    application = (
        PreReqAIApplication()
    )

    projector = (

        create_bootstrap_projector(
            application
        )
    )

    try:

        projector.project(
            recent_session_limit=-1,
        )

        assert False, (
            "expected ValueError"
        )

    except ValueError:

        pass

    try:

        projector.project(
            recent_activity_limit=-1,
        )

        assert False, (
            "expected ValueError"
        )

    except ValueError:

        pass

    projection = projector.project(

        recent_session_limit=0,

        recent_activity_limit=0,
    )

    assert projection.recent_sessions == []

    assert projection.recent_activity == []


def test_bootstrap_projection_is_read_only():

    application = (
        PreReqAIApplication()
    )

    populate_sessions(
        application,
        3,
    )

    before_session_count = len(

        application
        .session_manager
        .list_sessions()
    )

    before_activity_count = len(

        application
        .research_activity_store
        .list_all()
    )

    before_sequence = (

        application
        .research_workspace_change_feed
        .latest_sequence
    )

    application.research_workspace.get_bootstrap()

    application.research_workspace.get_bootstrap()

    after_session_count = len(

        application
        .session_manager
        .list_sessions()
    )

    after_activity_count = len(

        application
        .research_activity_store
        .list_all()
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

    assert (
        before_activity_count

        == after_activity_count
    )

    assert (
        before_sequence

        == after_sequence
    )


def test_gateway_exposes_bootstrap_projection():

    application = (
        PreReqAIApplication()
    )

    populate_sessions(
        application,
        1,
    )

    gateway_projection = (

        application
        .research_workspace
        .get_bootstrap(

            recent_session_limit=1,

            recent_activity_limit=1,
        )
    )

    direct_projection = (

        application
        .research_workspace_bootstrap_projector
        .project(

            recent_session_limit=1,

            recent_activity_limit=1,
        )
    )

    assert (

        gateway_projection.overview

        == direct_projection.overview
    )

    assert len(

        gateway_projection.recent_sessions

    ) == len(

        direct_projection.recent_sessions
    )

    assert (

        gateway_projection.readiness.status

        == direct_projection.readiness.status
    )


def test_serialization_is_fully_consumer_friendly():

    application = (
        PreReqAIApplication()
    )

    populate_sessions(
        application,
        1,
    )

    projection = (

        application
        .research_workspace
        .get_bootstrap()
    )

    payload = projection.to_dict()

    assert isinstance(
        payload["readiness"]["status"],
        str,
    )

    assert isinstance(
        payload["overview"]["total_sessions"],
        int,
    )

    for capability in (
        payload["capabilities"]
    ):

        assert isinstance(
            capability["name"],
            str,
        )

        assert isinstance(
            capability["enabled"],
            bool,
        )

    for session in (
        payload["recent_sessions"]
    ):

        assert isinstance(
            session["status"],
            str,
        )

    for event in (
        payload["recent_activity"]
    ):

        assert isinstance(
            event["activity_type"],
            str,
        )

    assert isinstance(
        payload["warnings"],
        list,
    )
