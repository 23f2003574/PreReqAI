from backend.session import (
    ResearchSessionStatus,
)

from frontend.src.app import (
    PreReqAIApplication,
)


def create_workspace():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(

        session_id="transformer-main",

        paper_title=(
            "Attention Is All You Need"
        ),
    )

    application.save_research_session(

        "transformer-main",

        paper_title=(
            "Attention Is All You Need"
        ),
    )

    application.update_research_session_profile(

        "transformer-main",

        display_name=(
            "Transformer Research"
        ),
    )

    root_checkpoint = (

        application
        .checkpoint_workflow_progress(

            "root-step"
        )
    )

    application.branch_research_checkpoint(

        root_checkpoint.id,

        branch_session_id=(
            "math-branch"
        ),

        display_name=(
            "Mathematical Approach"
        ),

        description=(

            "Explore mathematical "
            "prerequisites."
        ),
    )

    application.branch_research_checkpoint(

        root_checkpoint.id,

        branch_session_id=(
            "implementation-branch"
        ),

        display_name=(
            "Implementation Approach"
        ),
    )

    application.activate_research_session(

        "math-branch"
    )

    math_checkpoint = (

        application
        .checkpoint_workflow_progress(

            "math-step"
        )
    )

    application.branch_research_checkpoint(

        math_checkpoint.id,

        branch_session_id=(
            "spectral-branch"
        ),

        display_name=(
            "Spectral Derivation"
        ),
    )

    application.pause_research_session(

        "math-branch"
    )

    application.archive_research_session(

        "implementation-branch"
    )

    application.activate_research_session(

        session_id="diffusion-main",

        paper_title=(
            "Diffusion Models"
        ),
    )

    application.save_research_session(

        "diffusion-main",

        paper_title=(
            "Diffusion Models"
        ),
    )

    application.update_research_session_profile(

        "diffusion-main",

        display_name=(
            "Diffusion Research"
        ),
    )

    return application


def test_searches_sessions_by_human_metadata():

    application = (
        create_workspace()
    )

    page = (

        application
        .query_research_sessions(

            search="mathematical"
        )
    )

    assert page.total == 1

    assert (

        page.items[0]
        .session_id

        == "math-branch"
    )


def test_searches_sessions_by_description():

    application = (
        create_workspace()
    )

    page = (

        application
        .query_research_sessions(

            search="prerequisites"
        )
    )

    assert page.total == 1

    assert (

        page.items[0]
        .session_id

        == "math-branch"
    )


def test_filters_sessions_by_status():

    application = (
        create_workspace()
    )

    page = (

        application
        .query_research_sessions(

            statuses={
                "paused"
            }
        )
    )

    assert page.total == 1

    assert (

        page.items[0].status

        == (
            ResearchSessionStatus
            .PAUSED
        )
    )


def test_filters_archived_sessions():

    application = (
        create_workspace()
    )

    page = (

        application
        .query_research_sessions(

            archived=True
        )
    )

    assert page.total == 1

    assert (

        page.items[0]
        .session_id

        == (
            "implementation-branch"
        )
    )


def test_filters_root_research_sessions():

    application = (
        create_workspace()
    )

    page = (

        application
        .query_research_sessions(

            kinds={
                "root"
            }
        )
    )

    assert {

        item.session_id

        for item

        in page.items

    } == {

        "transformer-main",

        "diffusion-main",
    }


def test_filters_branch_research_sessions():

    application = (
        create_workspace()
    )

    page = (

        application
        .query_research_sessions(

            kinds={
                "branch"
            }
        )
    )

    assert {

        item.session_id

        for item

        in page.items

    } == {

        "math-branch",

        "implementation-branch",

        "spectral-branch",
    }


def test_filters_entire_research_lineage():

    application = (
        create_workspace()
    )

    page = (

        application
        .query_research_sessions(

            lineage_root_session_id=(

                "transformer-main"
            )
        )
    )

    assert {

        item.session_id

        for item

        in page.items

    } == {

        "transformer-main",

        "math-branch",

        "implementation-branch",

        "spectral-branch",
    }


def test_filters_direct_child_sessions():

    application = (
        create_workspace()
    )

    page = (

        application
        .query_research_sessions(

            direct_parent_session_id=(

                "transformer-main"
            )
        )
    )

    assert {

        item.session_id

        for item

        in page.items

    } == {

        "math-branch",

        "implementation-branch",
    }


def test_combines_session_filters():

    application = (
        create_workspace()
    )

    page = (

        application
        .query_research_sessions(

            search="approach",

            kinds={
                "branch"
            },

            archived=False,
        )
    )

    assert page.total == 1

    assert (

        page.items[0]
        .session_id

        == "math-branch"
    )


def test_sorts_sessions_by_name():

    application = (
        create_workspace()
    )

    page = (

        application
        .query_research_sessions(

            sort_order=(
                "name_ascending"
            )
        )
    )

    names = [

        item.display_name

        for item

        in page.items
    ]

    assert names == sorted(

        names,

        key=str.casefold,
    )


def test_paginates_research_sessions():

    application = (
        create_workspace()
    )

    page = (

        application
        .query_research_sessions(

            sort_order=(
                "name_ascending"
            ),

            offset=0,

            limit=2,
        )
    )

    assert page.total == 5

    assert page.returned == 2

    assert page.has_more is True

    assert page.next_offset == 2


def test_final_session_page_has_no_next_offset():

    application = (
        create_workspace()
    )

    page = (

        application
        .query_research_sessions(

            offset=4,

            limit=2,
        )
    )

    assert page.total == 5

    assert page.returned == 1

    assert page.has_more is False

    assert page.next_offset is None


def test_query_supports_sessions_without_profiles():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(

        session_id="legacy-session",

        paper_title=(
            "Legacy Research Paper"
        ),
    )

    application.save_research_session(

        "legacy-session",

        paper_title=(
            "Legacy Research Paper"
        ),
    )

    page = (

        application
        .query_research_sessions()
    )

    assert page.total == 1

    item = page.items[0]

    assert (

        item.display_name

        == "Legacy Research Paper"
    )

    assert (

        item.status

        == (
            ResearchSessionStatus
            .ACTIVE
        )
    )

    assert item.archived is False


def test_session_query_does_not_create_profiles():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(

        "legacy-session"
    )

    application.save_research_session(

        "legacy-session"
    )

    assert (

        application
        .research_session_profile(

            "legacy-session"
        )

        is None
    )

    application.query_research_sessions()

    assert (

        application
        .research_session_profile(

            "legacy-session"
        )

        is None
    )
