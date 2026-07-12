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
