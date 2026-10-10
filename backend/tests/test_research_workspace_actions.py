from backend.session import (
    ResearchWorkspaceAction,
    ResearchWorkspaceActionCatalog,
    ResearchWorkspaceActionProjector,
    ResearchWorkspaceActionScope,
    ResearchWorkspaceAttentionCategory,
    ResearchWorkspaceCapability,
    ResearchWorkspaceProjectionContext,
    ResearchWorkspaceReadinessAssessment,
    ResearchWorkspaceReadinessStatus,
)

from frontend.src.app import (
    PreReqAIApplication,
)


def make_readiness(

    status,

):

    return (

        ResearchWorkspaceReadinessAssessment(

            status=status,

            ready=(

                status

                != ResearchWorkspaceReadinessStatus
                .UNAVAILABLE
            ),

            blocking=(

                status

                == ResearchWorkspaceReadinessStatus
                .UNAVAILABLE
            ),

            checks=[],

            warnings=[],

            blocking_reasons=[],
        )
    )


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

    def create(

        self,

        *,

        diagnostics=None,

    ):

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

                diagnostics=diagnostics,
            )
        )


def create_projector(

    application,

    capability_registry=None,

    readiness_assessor=None,

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

                or FakeReadinessAssessor(

                    make_readiness(

                        ResearchWorkspaceReadinessStatus
                        .READY
                    )
                )
            ),

            integrity_auditor=(

                application
                .research_workspace_integrity_auditor
            ),

            insights_service=(

                application
                .research_workspace_insights_service
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

        ResearchWorkspaceActionProjector(

            action_catalog=(
                ResearchWorkspaceActionCatalog()
            ),

            context_factory=(
                context_factory
            ),
        )
    )


def create_active_session(

    application,

    session_id="session-1",

):

    application.activate_research_session(
        session_id
    )

    application.save_research_session(
        session_id,

        paper_title="Attention Is "
        "All You Need",
    )

    application.update_research_session_profile(

        session_id,

        display_name="Session One",
    )

    return session_id


def test_action_catalog_lists_known_actions():

    catalog = (
        ResearchWorkspaceActionCatalog()
    )

    actions = catalog.list_actions()

    identifiers = [

        descriptor.action.value

        for descriptor

        in actions
    ]

    assert len(
        identifiers
    ) == len(
        set(
            identifiers
        )
    )

    assert (
        "create_branch"

        in identifiers
    )

    assert (
        "review_integrity"

        in identifiers
    )


def test_action_lookup_works():

    catalog = (
        ResearchWorkspaceActionCatalog()
    )

    by_enum = catalog.get_action(

        ResearchWorkspaceAction
        .CREATE_BRANCH
    )

    by_string = catalog.get_action(
        "create_branch"
    )

    assert by_enum is by_string

    assert (

        catalog.get_action(
            "does_not_exist"
        )

        is None
    )


def test_catalog_filters_by_scope():

    catalog = (
        ResearchWorkspaceActionCatalog()
    )

    session_actions = (

        catalog.list_by_scope(

            ResearchWorkspaceActionScope
            .SESSION
        )
    )

    assert len(
        session_actions
    ) > 0

    assert all(

        descriptor.scope

        == ResearchWorkspaceActionScope
        .SESSION

        for descriptor

        in session_actions
    )


def test_catalog_filters_by_capability():

    catalog = (
        ResearchWorkspaceActionCatalog()
    )

    lineage_actions = (

        catalog.list_by_capability(

            ResearchWorkspaceCapability
            .LINEAGE
        )
    )

    identifiers = {

        descriptor.action.value

        for descriptor

        in lineage_actions
    }

    assert identifiers == {

        "create_branch",

        "view_lineage",
    }


def test_unsupported_capability_blocks_associated_action():

    application = (
        PreReqAIApplication()
    )

    session_id = (
        create_active_session(
            application
        )
    )

    capabilities = (

        application
        .research_workspace_capabilities
    )

    capabilities.get_capability(
        "lineage"
    ).enabled = False

    projector = (

        create_projector(
            application,

            capability_registry=(
                capabilities
            ),
        )
    )

    projection = (

        projector
        .project_session_actions(

            session_id,

            include_unavailable=True,
        )
    )

    by_action = {

        item.action.value: item

        for item

        in projection.actions
    }

    assert (
        by_action[
            "create_branch"
        ].available

        is False
    )

    assert (
        "not supported"

        in by_action[
            "create_branch"
        ].reason
    )


def test_unavailable_workspace_blocks_normal_mutations():

    application = (
        PreReqAIApplication()
    )

    projector = (

        create_projector(
            application,

            readiness_assessor=(

                FakeReadinessAssessor(

                    make_readiness(

                        ResearchWorkspaceReadinessStatus
                        .UNAVAILABLE
                    )
                )
            ),
        )
    )

    projection = (

        projector
        .project_workspace_actions(
            include_unavailable=True,
        )
    )

    by_action = {

        item.action.value: item

        for item

        in projection.actions
    }

    assert (
        by_action[
            "create_session"
        ].available

        is False
    )

    assert (
        by_action[
            "import_snapshot"
        ].available

        is False
    )


def test_diagnostic_read_actions_can_remain_available():

    application = (
        PreReqAIApplication()
    )

    projector = (

        create_projector(
            application,

            readiness_assessor=(

                FakeReadinessAssessor(

                    make_readiness(

                        ResearchWorkspaceReadinessStatus
                        .UNAVAILABLE
                    )
                )
            ),
        )
    )

    projection = (

        projector
        .project_workspace_actions(
            include_unavailable=True,
        )
    )

    by_action = {

        item.action.value: item

        for item

        in projection.actions
    }

    assert (
        by_action[
            "review_integrity"
        ].available

        is True
    )


def test_degraded_workspace_does_not_automatically_block_all_actions():

    application = (
        PreReqAIApplication()
    )

    projector = (

        create_projector(
            application,

            readiness_assessor=(

                FakeReadinessAssessor(

                    make_readiness(

                        ResearchWorkspaceReadinessStatus
                        .DEGRADED
                    )
                )
            ),
        )
    )

    projection = (

        projector
        .project_workspace_actions()
    )

    identifiers = {

        item.action.value

        for item

        in projection.actions
    }

    assert (
        "create_session"

        in identifiers
    )


def test_session_lifecycle_rules_affect_action_availability():

    application = (
        PreReqAIApplication()
    )

    session_id = (
        create_active_session(
            application
        )
    )

    projector = (
        create_projector(
            application
        )
    )

    active_projection = (

        projector
        .project_session_actions(
            session_id,
        )
    )

    active_ids = {

        item.action.value

        for item

        in active_projection.actions
    }

    assert (
        "pause_session"

        in active_ids
    )

    assert (
        "resume_session"

        not in active_ids
    )

    application.update_research_session_profile(

        session_id,

        status="paused",
    )

    paused_projection = (

        projector
        .project_session_actions(
            session_id,
        )
    )

    paused_ids = {

        item.action.value

        for item

        in paused_projection.actions
    }

    assert (
        "resume_session"

        in paused_ids
    )

    assert (
        "pause_session"

        not in paused_ids
    )


def test_unknown_session_is_handled_cleanly():

    application = (
        PreReqAIApplication()
    )

    projector = (
        create_projector(
            application
        )
    )

    try:

        projector.project_session_actions(
            "does-not-exist",
        )

        assert False, (
            "expected ValueError"
        )

    except ValueError as error:

        assert (
            "does-not-exist"

            in str(
                error
            )
        )


def test_include_unavailable_false_returns_only_available_actions():

    application = (
        PreReqAIApplication()
    )

    projector = (

        create_projector(
            application,

            readiness_assessor=(

                FakeReadinessAssessor(

                    make_readiness(

                        ResearchWorkspaceReadinessStatus
                        .UNAVAILABLE
                    )
                )
            ),
        )
    )

    projection = (

        projector
        .project_workspace_actions(
            include_unavailable=False,
        )
    )

    assert all(

        item.available

        for item

        in projection.actions
    )

    assert (

        "create_session"

        not in {

            item.action.value

            for item

            in projection.actions
        }
    )


def test_include_unavailable_true_preserves_reasons():

    application = (
        PreReqAIApplication()
    )

    projector = (

        create_projector(
            application,

            readiness_assessor=(

                FakeReadinessAssessor(

                    make_readiness(

                        ResearchWorkspaceReadinessStatus
                        .UNAVAILABLE
                    )
                )
            ),
        )
    )

    projection = (

        projector
        .project_workspace_actions(
            include_unavailable=True,
        )
    )

    blocked = [

        item

        for item

        in projection.actions

        if not item.available
    ]

    assert len(
        blocked
    ) > 0

    assert all(

        item.reason is not None

        for item

        in blocked
    )


def test_action_ordering_is_deterministic():

    application = (
        PreReqAIApplication()
    )

    projector = (
        create_projector(
            application
        )
    )

    first = (

        projector
        .project_workspace_actions(
            include_unavailable=True,
        )
    )

    second = (

        projector
        .project_workspace_actions(
            include_unavailable=True,
        )
    )

    first_order = [

        item.action.value

        for item

        in first.actions
    ]

    second_order = [

        item.action.value

        for item

        in second.actions
    ]

    assert first_order == second_order


def test_attention_actions_use_the_stable_action_vocabulary():

    application = (
        PreReqAIApplication()
    )

    create_active_session(
        application
    )

    catalog = (

        application
        .research_workspace_action_catalog
    )

    attention = (

        application
        .research_workspace_attention_projector
        .project()
    )

    integrity_items = [

        item

        for item

        in attention.items

        if (

            item.category

            == ResearchWorkspaceAttentionCategory
            .INTEGRITY
        )
    ]

    for item in integrity_items:

        assert (

            catalog.get_action(
                item.action
            )

            is not None
        )


def test_gateway_exposes_workspace_and_session_action_discovery():

    application = (
        PreReqAIApplication()
    )

    session_id = (
        create_active_session(
            application
        )
    )

    workspace_projection = (

        application
        .research_workspace
        .list_workspace_actions()
    )

    direct_workspace_projection = (

        application
        .research_workspace_action_projector
        .project_workspace_actions()
    )

    assert (

        {
            item.action.value

            for item

            in workspace_projection.actions
        }

        == {
            item.action.value

            for item

            in direct_workspace_projection.actions
        }
    )

    session_projection = (

        application
        .research_workspace
        .list_session_actions(
            session_id
        )
    )

    assert (
        session_projection.entity_id

        == session_id
    )


def test_bootstrap_includes_only_bounded_workspace_actions():

    application = (
        PreReqAIApplication()
    )

    create_active_session(
        application
    )

    bootstrap = (

        application
        .research_workspace
        .get_bootstrap()
    )

    assert len(
        bootstrap.workspace_actions
    ) > 0

    assert all(

        item.action.value

        != "pause_session"

        for item

        in bootstrap.workspace_actions
    )


def test_action_projection_is_read_only():

    application = (
        PreReqAIApplication()
    )

    session_id = (
        create_active_session(
            application
        )
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

    before_findings = len(

        application
        .research_workspace_integrity_auditor
        .audit()
        .findings
    )

    application.research_workspace.list_workspace_actions(
        include_unavailable=True,
    )

    application.research_workspace.list_session_actions(
        session_id,

        include_unavailable=True,
    )

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

    after_findings = len(

        application
        .research_workspace_integrity_auditor
        .audit()
        .findings
    )

    assert (
        before_session_count

        == after_session_count
    )

    assert (
        before_activity_count

        == after_activity_count
    )

    assert before_sequence == after_sequence

    assert before_findings == after_findings


def test_serialization_uses_primitive_values():

    application = (
        PreReqAIApplication()
    )

    session_id = (
        create_active_session(
            application
        )
    )

    projection = (

        application
        .research_workspace
        .list_session_actions(
            session_id,

            include_unavailable=True,
        )
    )

    payload = projection.to_dict()

    assert payload["scope"] == "session"

    for item in payload["actions"]:

        assert isinstance(
            item["action"],
            str,
        )

        assert isinstance(
            item["descriptor"]["scope"],
            str,
        )

        capability = (
            item["descriptor"][
                "capability"
            ]
        )

        assert (

            capability is None

            or isinstance(
                capability,
                str,
            )
        )
