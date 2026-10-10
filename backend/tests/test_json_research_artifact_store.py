from backend.session import (

    JsonResearchArtifactStore,

    ResearchArtifact,

    ResearchArtifactType,
)


def test_artifact_survives_store_recreation(

    tmp_path,

):

    path = (

        tmp_path

        / "artifacts.json"
    )

    first_store = (

        JsonResearchArtifactStore(
            path
        )
    )

    artifact = ResearchArtifact(

        session_id="session-1",

        object_id="attention",

        artifact_type=(

            ResearchArtifactType
            .EXPLANATION
        ),

        content=(

            "Persistent explanation"
        ),
    )

    first_store.save(
        artifact
    )

    second_store = (

        JsonResearchArtifactStore(
            path
        )
    )

    restored = (

        second_store.get(

            artifact.id
        )
    )

    assert restored is not None

    assert (

        restored.content

        == (
            "Persistent explanation"
        )
    )

    assert (

        restored.artifact_type

        == (
            ResearchArtifactType
            .EXPLANATION
        )
    )


def test_lists_artifacts_for_session_and_object(

    tmp_path,

):

    path = (

        tmp_path

        / "artifacts.json"
    )

    store = (

        JsonResearchArtifactStore(
            path
        )
    )

    first = ResearchArtifact(

        session_id="session-1",

        object_id="attention",

        artifact_type=(

            ResearchArtifactType
            .EXPLANATION
        ),

        content="Explanation",
    )

    second = ResearchArtifact(

        session_id="session-1",

        object_id="bert",

        artifact_type=(

            ResearchArtifactType
            .EXPLANATION
        ),

        content="BERT explanation",
    )

    store.save(first)

    store.save(second)

    assert (

        len(
            store.list_for_session(
                "session-1"
            )
        )

        == 2
    )

    assert (

        len(
            store.list_for_object(
                "session-1",

                "attention",
            )
        )

        == 1
    )
