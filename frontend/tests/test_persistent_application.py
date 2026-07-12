from backend.session import (
    ResearchCheckpointReason,
)

from frontend.src.persistent_app import (
    create_persistent_application,
)


def test_research_state_survives_application_recreation(

    tmp_path,

):

    data_directory = (

        tmp_path

        / "prereqai-data"
    )

    first_app = (

        create_persistent_application(

            data_directory
        )
    )

    first_app.activate_research_session(

        session_id="session-1",

        paper_id="paper-1",

        paper_title=(
            "Example Paper"
        ),
    )

    artifact = (

        first_app
        .save_interaction_artifact(

            interaction_id=(
                "interaction-1"
            ),

            session_id=(
                "session-1"
            ),

            object_id="attention",

            action="explain",

            content=(

                "Persistent "
                "attention explanation"
            ),
        )
    )

    second_app = (

        create_persistent_application(

            data_directory
        )
    )

    session = (

        second_app
        .get_research_session(

            "session-1"
        )
    )

    restored_artifact = (

        second_app
        .artifact_manager
        .get(

            artifact.id
        )
    )

    links = (

        second_app
        .interaction_artifact_correlations
        .links_for_interaction(

            "interaction-1"
        )
    )

    assert session is not None

    assert (

        artifact.id

        in session.artifact_ids
    )

    assert (

        restored_artifact

        is not None
    )

    assert (

        restored_artifact.content

        == (
            "Persistent "
            "attention explanation"
        )
    )

    assert len(links) == 1

    assert (

        links[0].artifact_id

        == artifact.id
    )


def test_checkpoint_history_survives_application_recreation(

    tmp_path,

):

    data_directory = (

        tmp_path

        / "prereqai-data"
    )

    first_app = (

        create_persistent_application(

            data_directory
        )
    )

    first_app.activate_research_session(

        session_id="session-1",

        paper_id="paper-1",

        paper_title=(
            "Example Paper"
        ),
    )

    first_app.checkpoint_workflow_progress(

        "step-1"
    )

    first_app.checkpoint_section(

        "section-2"
    )

    first_app.checkpoint_before_background()

    first_checkpoints = (

        first_app
        .research_checkpoints(

            "session-1"
        )
    )

    assert (

        len(
            first_checkpoints
        )

        == 3
    )

    second_app = (

        create_persistent_application(

            data_directory
        )
    )

    restored_checkpoints = (

        second_app
        .research_checkpoints(

            "session-1"
        )
    )

    assert (

        len(
            restored_checkpoints
        )

        == 3
    )

    assert (

        [
            checkpoint.reason

            for checkpoint

            in restored_checkpoints
        ]

        == [

            ResearchCheckpointReason
            .WORKFLOW_PROGRESS,

            ResearchCheckpointReason
            .SECTION_CHANGED,

            ResearchCheckpointReason
            .APPLICATION_BACKGROUND,
        ]
    )


def test_checkpoint_timeline_continues_after_restart(

    tmp_path,

):

    data_directory = (

        tmp_path

        / "prereqai-data"
    )

    first_app = (

        create_persistent_application(

            data_directory
        )
    )

    first_app.activate_research_session(

        "session-1"
    )

    first_app.checkpoint_workflow_progress(

        "step-1"
    )

    second_app = (

        create_persistent_application(

            data_directory
        )
    )

    second_app.activate_research_session(

        "session-1"
    )

    second_app.checkpoint_workflow_progress(

        "step-2"
    )

    checkpoints = (

        second_app
        .research_checkpoints(

            "session-1"
        )
    )

    assert len(checkpoints) == 2

    assert (

        checkpoints[0]
        .metadata[
            "step_id"
        ]

        == "step-1"
    )

    assert (

        checkpoints[1]
        .metadata[
            "step_id"
        ]

        == "step-2"
    )
