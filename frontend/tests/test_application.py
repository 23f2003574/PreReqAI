from frontend.src import (
    PreReqAIApplication,
)

from frontend.src.workspace import (
    VisualResearchWorkspace,
)


def test_application_creates_workspace():

    application = (
        PreReqAIApplication()
    )

    assert isinstance(

        application.workspace,

        VisualResearchWorkspace,
    )


def test_application_saves_and_loads_research_session():

    application = (
        PreReqAIApplication()
    )

    saved = (

        application
        .save_research_session(

            session_id="session-1",

            paper_id="paper-1",

            paper_title=(
                "Example Paper"
            ),
        )
    )

    assert (

        saved.session_id

        == "session-1"
    )

    loaded = (

        application
        .get_research_session(
            "session-1"
        )
    )

    assert (

        loaded.paper_title

        == "Example Paper"
    )

    assert (

        len(
            application
            .research_sessions()
        )

        == 1
    )
