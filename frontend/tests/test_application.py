from backend.interaction.research_object import (
    ResearchObject,
)

from backend.interaction.research_object_type import (
    ResearchObjectType,
)

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


def test_application_restores_selected_object_after_restart():

    application = (
        PreReqAIApplication()
    )

    research_object = ResearchObject(

        id="attention",

        object_type=(
            ResearchObjectType.CONCEPT
        ),

        title="Attention",

        description=(
            "Attention mechanism"
        ),
    )

    application.workspace.inspect_object(

        research_object
    )

    application.save_research_session(

        session_id="session-1",

        paper_title="Example Paper",
    )

    application.workspace.state.selected_object = None

    application.register_research_objects(
        [research_object]
    )

    result = (

        application
        .restore_research_session(
            "session-1"
        )
    )

    assert (

        result.restored_object

        is research_object
    )

    assert (

        application.workspace.state
        .selected_object

        is research_object
    )


def test_application_saves_learning_artifact_and_references_it_in_session():

    application = (
        PreReqAIApplication()
    )

    artifact = (

        application
        .save_learning_artifact(

            session_id="session-1",

            object_id="attention",

            action="explain",

            content=(
                "Attention explanation"
            ),
        )
    )

    assert artifact.version == 1

    assert (

        len(

            application
            .research_artifacts(
                "session-1"
            )
        )

        == 1
    )

    assert (

        len(

            application
            .research_artifacts_for_object(
                "session-1",

                "attention",
            )
        )

        == 1
    )

    saved = (

        application
        .save_research_session(

            session_id="session-1",

            paper_title=(
                "Example Paper"
            ),
        )
    )

    assert (

        saved.artifact_ids

        == [
            artifact.id
        ]
    )
