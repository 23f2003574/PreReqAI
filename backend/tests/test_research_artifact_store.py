from backend.session import (

    InMemoryResearchArtifactStore,

    ResearchArtifact,

    ResearchArtifactType,
)


def test_saves_and_loads_artifact():

    store = (
        InMemoryResearchArtifactStore()
    )

    artifact = ResearchArtifact(

        session_id="session-1",

        object_id="attention",

        artifact_type=(

            ResearchArtifactType
            .EXPLANATION
        ),

        content=(

            "Attention allows a model "
            "to weigh relevant tokens."
        ),
    )

    saved = store.save(
        artifact
    )

    loaded = store.get(
        saved.id
    )

    assert loaded is not None

    assert (

        loaded.object_id

        == "attention"
    )

    assert (

        loaded.content

        == artifact.content
    )


def test_lists_artifacts_for_session():

    store = (
        InMemoryResearchArtifactStore()
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

        session_id="session-2",

        object_id="bert",

        artifact_type=(

            ResearchArtifactType
            .EXPLANATION
        ),

        content="BERT explanation",
    )

    store.save(first)

    store.save(second)

    artifacts = (

        store.list_for_session(

            "session-1"
        )
    )

    assert (

        len(artifacts)

        == 1
    )

    assert (

        artifacts[0].object_id

        == "attention"
    )


def test_deletes_artifact():

    store = (
        InMemoryResearchArtifactStore()
    )

    artifact = ResearchArtifact(

        session_id="session-1",

        object_id="attention",

        artifact_type=(

            ResearchArtifactType
            .EXPLANATION
        ),

        content="Explanation",
    )

    saved = store.save(
        artifact
    )

    deleted = store.delete(
        saved.id
    )

    assert deleted is True

    assert (

        store.get(
            saved.id
        )

        is None
    )
