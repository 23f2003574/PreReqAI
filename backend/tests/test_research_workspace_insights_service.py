from datetime import (
    datetime,
    timedelta,
    timezone,
)

from backend.session import (
    InMemoryResearchActivityStore,
    InMemoryResearchCollectionStore,
    InMemoryResearchSessionBranchStore,
    InMemoryResearchSessionProfileStore,
    InMemoryResearchSessionStore,
    InMemoryResearchTagStore,
    ResearchActivityEvent,
    ResearchActivityType,
    ResearchSessionLineageService,
    ResearchSessionManager,
    ResearchSessionProfile,
    ResearchSessionSnapshot,
    ResearchSessionStatus,
    ResearchWorkspaceInsightsService,
)

from frontend.src.app import (
    PreReqAIApplication,
)


def create_workspace():

    application = (
        PreReqAIApplication()
    )

    for session_id in (

        "session-a",

        "session-b",

        "session-c",
    ):

        application.activate_research_session(

            session_id
        )

        application.save_research_session(

            session_id
        )

    return application


def create_workspace_with_branch():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(
        "root"
    )

    checkpoint = (

        application
        .checkpoint_workflow_progress(

            "step-a"
        )
    )

    application.branch_research_checkpoint(

        checkpoint.id,

        branch_session_id=(
            "branch-a"
        ),
    )

    return application


def create_deep_lineage_workspace():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(
        "root"
    )

    cp1 = (

        application
        .checkpoint_workflow_progress(
            "s1"
        )
    )

    application.branch_research_checkpoint(

        cp1.id,

        branch_session_id=(
            "branch-a"
        ),
    )

    application.activate_research_session(
        "branch-a"
    )

    cp2 = (

        application
        .checkpoint_workflow_progress(
            "s2"
        )
    )

    application.branch_research_checkpoint(

        cp2.id,

        branch_session_id=(
            "branch-b"
        ),
    )

    application.activate_research_session(
        "branch-b"
    )

    cp3 = (

        application
        .checkpoint_workflow_progress(
            "s3"
        )
    )

    application.branch_research_checkpoint(

        cp3.id,

        branch_session_id=(
            "branch-c"
        ),
    )

    return application


def create_branching_workspace():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(
        "root"
    )

    cp = (

        application
        .checkpoint_workflow_progress(
            "s1"
        )
    )

    application.branch_research_checkpoint(

        cp.id,

        branch_session_id=(
            "branch-a"
        ),
    )

    application.branch_research_checkpoint(

        cp.id,

        branch_session_id=(
            "branch-b"
        ),
    )

    application.branch_research_checkpoint(

        cp.id,

        branch_session_id=(
            "branch-c"
        ),
    )

    application.activate_research_session(
        "branch-a"
    )

    cp2 = (

        application
        .checkpoint_workflow_progress(
            "s2"
        )
    )

    application.branch_research_checkpoint(

        cp2.id,

        branch_session_id=(
            "branch-d"
        ),
    )

    return application


def _build_low_level_service(

    clock=None,

):

    session_store = (
        InMemoryResearchSessionStore()
    )

    profile_store = (
        InMemoryResearchSessionProfileStore()
    )

    branch_store = (
        InMemoryResearchSessionBranchStore()
    )

    tag_store = (
        InMemoryResearchTagStore()
    )

    collection_store = (
        InMemoryResearchCollectionStore()
    )

    activity_store = (
        InMemoryResearchActivityStore()
    )

    service = (

        ResearchWorkspaceInsightsService(

            session_manager=(

                ResearchSessionManager(
                    session_store
                )
            ),

            profile_store=(
                profile_store
            ),

            lineage_service=(

                ResearchSessionLineageService(

                    branch_store=(
                        branch_store
                    )
                )
            ),

            tag_store=(
                tag_store
            ),

            collection_store=(
                collection_store
            ),

            activity_store=(
                activity_store
            ),

            clock=clock,
        )
    )

    return (

        service,

        session_store,

        profile_store,

        activity_store,
    )


def _add_session_with_activity(

    session_store,

    profile_store,

    activity_store,

    session_id,

    status=(
        ResearchSessionStatus.ACTIVE
    ),

    archived=False,

    activity_at=None,

):

    session_store.save(

        ResearchSessionSnapshot(

            session_id=session_id
        )
    )

    profile_store.save(

        ResearchSessionProfile(

            session_id=session_id,

            status=status,

            archived=archived,
        )
    )

    if activity_at is not None:

        activity_store.append(

            ResearchActivityEvent(

                id=(

                    f"event-{session_id}"
                ),

                activity_type=(

                    ResearchActivityType
                    .SESSION_CREATED
                ),

                occurred_at=(
                    activity_at
                ),

                session_id=session_id,
            )
        )


def test_empty_workspace_has_zeroed_insights():

    application = (
        PreReqAIApplication()
    )

    insights = (

        application
        .research_workspace_insights()
    )

    assert (

        insights.overview
        .total_sessions

        == 0
    )

    assert (

        insights.lineage
        .maximum_depth

        == 0
    )

    assert (

        insights.lineage
        .average_depth

        == 0.0
    )

    assert (

        insights.lineage
        .deepest_session_id

        is None
    )

    assert insights.top_tags == []

    assert (

        insights.largest_collections

        == []
    )

    assert (

        insights.recently_active_sessions

        == []
    )

    assert (

        insights.dormant_sessions

        == []
    )


def test_counts_sessions_by_lifecycle_status():

    application = (
        create_workspace()
    )

    application.update_research_session_profile(

        "session-a",

        status="active",
    )

    application.pause_research_session(
        "session-b"
    )

    application.update_research_session_profile(

        "session-c",

        status="active",
    )

    insights = (

        application
        .research_workspace_insights()
    )

    assert (

        insights.lifecycle
        .counts["active"]

        == 2
    )

    assert (

        insights.lifecycle
        .counts["paused"]

        == 1
    )


def test_counts_root_and_branch_sessions():

    application = (
        create_workspace_with_branch()
    )

    insights = (

        application
        .research_workspace_insights()
    )

    assert (

        insights.overview
        .root_sessions

        == 1
    )

    assert (

        insights.overview
        .branch_sessions

        == 1
    )


def test_identifies_deepest_research_session():

    application = (
        create_deep_lineage_workspace()
    )

    insights = (

        application
        .research_workspace_insights()
    )

    assert (

        insights.lineage
        .maximum_depth

        == 3
    )

    assert (

        insights.lineage
        .deepest_session_id

        == "branch-c"
    )


def test_identifies_most_branched_session():

    application = (
        create_branching_workspace()
    )

    insights = (

        application
        .research_workspace_insights()
    )

    assert (

        insights.lineage
        .most_branched_session_id

        == "root"
    )

    assert (

        insights.lineage
        .most_branched_direct_children

        == 3
    )


def test_ranks_tags_by_session_usage():

    application = (
        create_workspace()
    )

    application.tag_research_session(

        "session-a",

        "transformers",
    )

    application.tag_research_session(

        "session-b",

        "transformers",
    )

    application.tag_research_session(

        "session-c",

        "math-heavy",
    )

    insights = (

        application
        .research_workspace_insights()
    )

    assert (

        insights.top_tags[0]
        .tag_name

        == "transformers"
    )

    assert (

        insights.top_tags[0]
        .session_count

        == 2
    )


def test_ranks_collections_by_membership():

    application = (
        create_workspace()
    )

    large = (

        application
        .create_research_collection(

            "Large Collection"
        )
    )

    small = (

        application
        .create_research_collection(

            "Small Collection"
        )
    )

    for session_id in [

        "session-a",

        "session-b",

        "session-c",
    ]:

        application.add_research_session_to_collection(

            large.id,

            session_id,
        )

    application.add_research_session_to_collection(

        small.id,

        "session-a",
    )

    insights = (

        application
        .research_workspace_insights()
    )

    assert (

        insights.largest_collections[0]
        .collection_id

        == large.id
    )

    assert (

        insights.largest_collections[0]
        .session_count

        == 3
    )


def test_counts_activity_in_time_windows():

    now = datetime(

        2026,
        7,
        13,
        12,
        0,

        tzinfo=timezone.utc,
    )

    (

        service,

        session_store,

        profile_store,

        activity_store,

    ) = (

        _build_low_level_service(

            clock=lambda: now
        )
    )

    for index, delta in enumerate([

        timedelta(hours=1),

        timedelta(days=3),

        timedelta(days=20),

        timedelta(days=60),
    ]):

        activity_store.append(

            ResearchActivityEvent(

                id=f"event-{index}",

                activity_type=(

                    ResearchActivityType
                    .SESSION_CREATED
                ),

                occurred_at=(

                    now - delta
                ),

                session_id="session-a",
            )
        )

    insights = (
        service.build_insights()
    )

    assert (

        insights.activity
        .events_last_24_hours

        == 1
    )

    assert (

        insights.activity
        .events_last_7_days

        == 2
    )

    assert (

        insights.activity
        .events_last_30_days

        == 3
    )

    assert (

        insights.activity
        .total_events

        == 4
    )


def test_recently_active_sessions_are_newest_first():

    (

        service,

        session_store,

        profile_store,

        activity_store,

    ) = (
        _build_low_level_service()
    )

    base_time = datetime(

        2026,
        7,
        13,
        12,
        0,

        tzinfo=timezone.utc,
    )

    for index, session_id in enumerate([

        "session-a",

        "session-b",

        "session-c",
    ]):

        _add_session_with_activity(

            session_store,

            profile_store,

            activity_store,

            session_id,

            activity_at=(

                base_time

                + timedelta(
                    minutes=index
                )
            ),
        )

    insights = (
        service.build_insights()
    )

    assert [

        item.session_id

        for item

        in insights
        .recently_active_sessions

    ] == [

        "session-c",

        "session-b",

        "session-a",
    ]


def test_identifies_dormant_active_sessions():

    now = datetime(

        2026,
        7,
        13,
        12,
        0,

        tzinfo=timezone.utc,
    )

    (

        service,

        session_store,

        profile_store,

        activity_store,

    ) = (

        _build_low_level_service(

            clock=lambda: now
        )
    )

    _add_session_with_activity(

        session_store,

        profile_store,

        activity_store,

        "session-recent",

        activity_at=(

            now
            - timedelta(days=5)
        ),
    )

    _add_session_with_activity(

        session_store,

        profile_store,

        activity_store,

        "session-dormant",

        activity_at=(

            now
            - timedelta(days=45)
        ),
    )

    insights = (

        service.build_insights(

            dormant_after_days=30
        )
    )

    dormant_ids = {

        item.session_id

        for item

        in insights
        .dormant_sessions
    }

    assert (

        "session-dormant"

        in dormant_ids
    )

    assert (

        "session-recent"

        not in dormant_ids
    )


def test_completed_sessions_are_not_marked_dormant():

    now = datetime(

        2026,
        7,
        13,
        12,
        0,

        tzinfo=timezone.utc,
    )

    (

        service,

        session_store,

        profile_store,

        activity_store,

    ) = (

        _build_low_level_service(

            clock=lambda: now
        )
    )

    _add_session_with_activity(

        session_store,

        profile_store,

        activity_store,

        "session-old",

        status=(

            ResearchSessionStatus
            .COMPLETED
        ),

        activity_at=(

            now
            - timedelta(days=90)
        ),
    )

    insights = (

        service.build_insights(

            dormant_after_days=30
        )
    )

    assert (

        "session-old"

        not in {

            item.session_id

            for item

            in insights
            .dormant_sessions
        }
    )


def test_archived_sessions_are_not_marked_dormant():

    now = datetime(

        2026,
        7,
        13,
        12,
        0,

        tzinfo=timezone.utc,
    )

    (

        service,

        session_store,

        profile_store,

        activity_store,

    ) = (

        _build_low_level_service(

            clock=lambda: now
        )
    )

    _add_session_with_activity(

        session_store,

        profile_store,

        activity_store,

        "session-old",

        archived=True,

        activity_at=(

            now
            - timedelta(days=90)
        ),
    )

    insights = (

        service.build_insights(

            dormant_after_days=30
        )
    )

    assert (

        "session-old"

        not in {

            item.session_id

            for item

            in insights
            .dormant_sessions
        }
    )


def test_workspace_insights_serializes_to_dict():

    application = (
        create_workspace()
    )

    insights = (

        application
        .research_workspace_insights()
    )

    payload = (
        insights.to_dict()
    )

    assert "overview" in payload

    assert "lifecycle" in payload

    assert "lineage" in payload

    assert "activity" in payload

    assert "top_tags" in payload

    assert (

        "largest_collections"

        in payload
    )

    assert (

        "recently_active_sessions"

        in payload
    )

    assert (

        "dormant_sessions"

        in payload
    )
