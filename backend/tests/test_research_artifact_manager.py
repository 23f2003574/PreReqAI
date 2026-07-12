from backend.session import (

    InMemoryResearchArtifactStore,

    ResearchArtifactManager,

    ResearchArtifactType,
)


def test_creates_research_artifact():

    manager = (

        ResearchArtifactManager(

            InMemoryResearchArtifactStore()
        )
    )

    artifact = manager.create(

        session_id="session-1",

        object_id="attention",

        artifact_type=(

            ResearchArtifactType
            .EXPLANATION
        ),

        content="Attention explanation",

        action="explain",
    )

    assert (

        artifact.version

        == 1
    )

    assert (

        artifact.action

        == "explain"
    )


def test_versions_repeated_artifacts():

    manager = (

        ResearchArtifactManager(

            InMemoryResearchArtifactStore()
        )
    )

    first = manager.create(

        session_id="session-1",

        object_id="attention",

        artifact_type=(

            ResearchArtifactType
            .EXPLANATION
        ),

        content="First explanation",

        action="explain",
    )

    second = manager.create(

        session_id="session-1",

        object_id="attention",

        artifact_type=(

            ResearchArtifactType
            .EXPLANATION
        ),

        content="Second explanation",

        action="explain",
    )

    assert first.version == 1

    assert second.version == 2


def test_distinguishes_versions_by_action():

    manager = (

        ResearchArtifactManager(

            InMemoryResearchArtifactStore()
        )
    )

    explanation = manager.create(

        session_id="session-1",

        object_id="attention",

        artifact_type=(

            ResearchArtifactType
            .EXPLANATION
        ),

        content="Explanation",

        action="explain",
    )

    visualization = manager.create(

        session_id="session-1",

        object_id="attention",

        artifact_type=(

            ResearchArtifactType
            .VISUALIZATION
        ),

        content="Visualization",

        action="visualize",
    )

    assert explanation.version == 1

    assert visualization.version == 1

    assert (

        len(

            manager.for_object(
                "session-1",

                "attention",
            )
        )

        == 2
    )
