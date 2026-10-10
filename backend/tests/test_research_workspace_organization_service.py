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


def test_reuses_normalized_research_tag():

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

    first_tag = (

        application
        .tag_research_session(

            "session-a",

            "#Transformers",
        )
    )

    second_tag = (

        application
        .tag_research_session(

            "session-b",

            " transformers ",
        )
    )

    assert (

        first_tag.id

        == second_tag.id
    )


def test_tag_assignment_is_idempotent():

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

    tags = (

        application
        .research_session_tags(

            "session-a"
        )
    )

    assert len(tags) == 1


def test_session_supports_multiple_tags():

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

        "math-heavy",
    )

    names = {

        tag.name

        for tag

        in application
        .research_session_tags(

            "session-a"
        )
    }

    assert names == {

        "transformers",

        "math-heavy",
    }


def test_untagging_does_not_delete_reusable_tag():

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

    removed = (

        application
        .untag_research_session(

            "session-a",

            "transformers",
        )
    )

    assert removed is True

    assert (

        application
        .research_session_tags(

            "session-a"
        )

        == []
    )

    reused_tag = (

        application
        .tag_research_session(

            "session-a",

            "transformers",
        )
    )

    assert reused_tag is not None


def test_filters_sessions_matching_all_tags():

    application = (
        create_workspace()
    )

    application.tag_research_session(

        "session-a",

        "transformers",
    )

    application.tag_research_session(

        "session-a",

        "math-heavy",
    )

    application.tag_research_session(

        "session-b",

        "transformers",
    )

    page = (

        application
        .query_research_sessions(

            tag_names={
                "transformers",
                "math-heavy",
            },

            match_all_tags=True,
        )
    )

    assert [

        item.session_id

        for item

        in page.items

    ] == [

        "session-a"
    ]


def test_filters_sessions_matching_any_tag():

    application = (
        create_workspace()
    )

    application.tag_research_session(

        "session-a",

        "transformers",
    )

    application.tag_research_session(

        "session-b",

        "diffusion",
    )

    page = (

        application
        .query_research_sessions(

            tag_names={
                "transformers",
                "diffusion",
            },

            match_all_tags=False,
        )
    )

    assert {

        item.session_id

        for item

        in page.items

    } == {

        "session-a",

        "session-b",
    }


def test_adds_multiple_sessions_to_collection():

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

    application.add_research_session_to_collection(

        collection.id,

        "session-b",
    )

    session_ids = (

        application
        .workspace_organization_service
        .session_ids_in_collection(

            collection.id
        )
    )

    assert session_ids == [

        "session-a",

        "session-b",
    ]


def test_session_can_belong_to_multiple_collections():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(

        "session-a"
    )

    application.save_research_session(
        "session-a"
    )

    current = (

        application
        .create_research_collection(

            "Current Research"
        )
    )

    foundations = (

        application
        .create_research_collection(

            "DL Foundations"
        )
    )

    application.add_research_session_to_collection(

        current.id,

        "session-a",
    )

    application.add_research_session_to_collection(

        foundations.id,

        "session-a",
    )

    collections = (

        application
        .research_collections_for_session(

            "session-a"
        )
    )

    assert {

        collection.id

        for collection

        in collections

    } == {

        current.id,

        foundations.id,
    }


def test_deleting_collection_does_not_delete_sessions():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(

        "session-a"
    )

    application.save_research_session(
        "session-a"
    )

    collection = (

        application
        .create_research_collection(

            "Temporary Collection"
        )
    )

    application.add_research_session_to_collection(

        collection.id,

        "session-a",
    )

    application.workspace_organization_service.delete_collection(

        collection.id
    )

    session = (

        application
        .session_manager
        .load_session(

            "session-a"
        )
    )

    assert session is not None


def test_filters_sessions_by_collection():

    application = (
        create_workspace()
    )

    collection = (

        application
        .create_research_collection(

            "Priority Research"
        )
    )

    application.add_research_session_to_collection(

        collection.id,

        "session-a",
    )

    application.add_research_session_to_collection(

        collection.id,

        "session-c",
    )

    page = (

        application
        .query_research_sessions(

            collection_ids={
                collection.id
            }
        )
    )

    assert {

        item.session_id

        for item

        in page.items

    } == {

        "session-a",

        "session-c",
    }


def test_combines_tags_collections_and_status():

    application = (
        create_workspace()
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

    application.add_research_session_to_collection(

        collection.id,

        "session-b",
    )

    application.tag_research_session(

        "session-a",

        "math-heavy",
    )

    application.tag_research_session(

        "session-b",

        "implementation",
    )

    page = (

        application
        .query_research_sessions(

            collection_ids={
                collection.id
            },

            tag_names={
                "math-heavy"
            },

            statuses={
                "active"
            },

            archived=False,
        )
    )

    assert page.total == 1

    assert (

        page.items[0]
        .session_id

        == "session-a"
    )


def test_session_list_item_exposes_tags_and_collections():

    application = (
        create_workspace()
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

    application.tag_research_session(

        "session-a",

        "transformers",
    )

    page = (

        application
        .query_research_sessions(

            search="session-a"
        )
    )

    item = page.items[0]

    assert item.tag_names == [
        "transformers",
    ]

    assert item.collection_ids == [
        collection.id,
    ]
