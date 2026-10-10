from backend.session import (
    ResearchActivityQuery,
    ResearchActivityType,
)

from frontend.src.app import (
    PreReqAIApplication,
)


def create_workspace_with_activity():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(

        "session-a"
    )

    application.save_research_session(
        "session-a"
    )

    application.tag_research_session(

        "session-a",

        "transformers",
    )

    return application


def test_session_created_recorded_once_per_session():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(

        "session-a"
    )

    application.save_research_session(
        "session-a"
    )

    application.activate_research_session(

        "session-a"
    )

    page = (

        application
        .research_session_activity(

            "session-a"
        )
    )

    created_events = [

        event

        for event

        in page.items

        if (

            event.activity_type

            == (
                ResearchActivityType
                .SESSION_CREATED
            )
        )
    ]

    activated_events = [

        event

        for event

        in page.items

        if (

            event.activity_type

            == (
                ResearchActivityType
                .SESSION_ACTIVATED
            )
        )
    ]

    assert len(created_events) == 1

    assert len(activated_events) == 2


def test_tag_assignment_records_activity():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(

        "session-a"
    )

    application.save_research_session(
        "session-a"
    )

    application.tag_research_session(

        "session-a",

        "#Math Heavy",
    )

    page = (

        application
        .research_session_activity(

            "session-a"
        )
    )

    matching = [

        event

        for event

        in page.items

        if (

            event.activity_type

            == (
                ResearchActivityType
                .TAG_ASSIGNED
            )
        )
    ]

    assert len(
        matching
    ) == 1

    assert (

        matching[0]
        .metadata[
            "tag_name"
        ]

        == "math-heavy"
    )


def test_duplicate_tag_assignment_does_not_duplicate_activity():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(

        "session-a"
    )

    application.save_research_session(
        "session-a"
    )

    application.tag_research_session(

        "session-a",

        "transformers",
    )

    application.tag_research_session(

        "session-a",

        "#Transformers",
    )

    page = (

        application
        .research_session_activity(

            "session-a"
        )
    )

    tag_events = [

        event

        for event

        in page.items

        if (

            event.activity_type

            == (
                ResearchActivityType
                .TAG_ASSIGNED
            )
        )
    ]

    assert len(
        tag_events
    ) == 1


def test_branch_creation_records_parent_and_child_activity():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(

        "session-main"
    )

    checkpoint = (

        application
        .checkpoint_workflow_progress(

            "root-step"
        )
    )

    application.branch_research_checkpoint(

        checkpoint.id,

        branch_session_id=(
            "session-spectral"
        ),
    )

    parent_activity = (

        application
        .research_session_activity(

            "session-main"
        )
    )

    child_activity = (

        application
        .research_session_activity(

            "session-spectral"
        )
    )

    assert any(

        event.activity_type

        == (
            ResearchActivityType
            .BRANCH_CREATED
        )

        for event

        in parent_activity.items
    )

    assert any(

        event.activity_type

        == (
            ResearchActivityType
            .BRANCH_CREATED
        )

        for event

        in child_activity.items
    )


def test_filters_activity_by_type():

    application = (
        create_workspace_with_activity()
    )

    query = (

        ResearchActivityQuery(

            activity_types={

                ResearchActivityType
                .TAG_ASSIGNED
            }
        )
    )

    page = (

        application
        .query_research_activity(

            query
        )
    )

    assert len(page.items) == 1

    assert all(

        event.activity_type

        == (
            ResearchActivityType
            .TAG_ASSIGNED
        )

        for event

        in page.items
    )


def test_workspace_recent_activity_unifies_subsystems():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(

        "session-a"
    )

    application.save_research_session(
        "session-a"
    )

    application.activate_research_session(

        "session-b"
    )

    application.save_research_session(
        "session-b"
    )

    application.update_research_session_profile(

        "session-a",

        display_name=(
            "Renamed Session"
        ),
    )

    application.tag_research_session(

        "session-b",

        "math-heavy",
    )

    collection = (

        application
        .create_research_collection(

            "Current Research"
        )
    )

    application.add_research_session_to_collection(

        collection.id,

        "session-a",
    )

    application.compare_research_sessions(

        "session-a",

        "session-b",
    )

    page = (

        application
        .recent_research_activity(

            page_size=20
        )
    )

    activity_types = {

        event.activity_type

        for event

        in page.items
    }

    assert (

        ResearchActivityType
        .SESSION_RENAMED

        in activity_types
    )

    assert (

        ResearchActivityType
        .TAG_ASSIGNED

        in activity_types
    )

    assert (

        ResearchActivityType
        .COLLECTION_CREATED

        in activity_types
    )

    assert (

        ResearchActivityType
        .COLLECTION_SESSION_ADDED

        in activity_types
    )

    assert (

        ResearchActivityType
        .SESSION_COMPARED

        in activity_types
    )
