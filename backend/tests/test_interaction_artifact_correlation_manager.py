from backend.session import (

    InMemoryInteractionArtifactLinkStore,

    InMemoryResearchArtifactStore,

    InteractionArtifactCorrelationManager,

    ResearchArtifact,

    ResearchArtifactType,
)


def test_resolves_exact_artifact_for_interaction():

    artifact_store = (

        InMemoryResearchArtifactStore()
    )

    link_store = (

        InMemoryInteractionArtifactLinkStore()
    )

    manager = (

        InteractionArtifactCorrelationManager(

            link_store=link_store,

            artifact_store=(
                artifact_store
            ),
        )
    )

    artifact = ResearchArtifact(

        session_id="session-1",

        object_id="attention",

        artifact_type=(

            ResearchArtifactType
            .EXPLANATION
        ),

        action="explain",

        content="First explanation",
    )

    artifact_store.save(
        artifact
    )

    manager.link(

        "interaction-1",

        artifact,
    )

    resolved = (

        manager
        .primary_artifact_for_interaction(

            "interaction-1"
        )
    )

    assert resolved is not None

    assert (

        resolved.id

        == artifact.id
    )

    assert (

        resolved.content

        == "First explanation"
    )


def test_interaction_can_link_multiple_artifacts():

    artifact_store = (

        InMemoryResearchArtifactStore()
    )

    link_store = (

        InMemoryInteractionArtifactLinkStore()
    )

    manager = (

        InteractionArtifactCorrelationManager(

            link_store=link_store,

            artifact_store=(
                artifact_store
            ),
        )
    )

    first = ResearchArtifact(

        session_id="session-1",

        object_id="equation-3",

        artifact_type=(

            ResearchArtifactType
            .EXPLANATION
        ),

        content="Derivation explanation",
    )

    second = ResearchArtifact(

        session_id="session-1",

        object_id="equation-3",

        artifact_type=(

            ResearchArtifactType
            .VISUALIZATION
        ),

        content="Visualization spec",
    )

    artifact_store.save(first)

    artifact_store.save(second)

    manager.link(
        "interaction-1",
        first,
    )

    manager.link(
        "interaction-1",
        second,
    )

    artifacts = (

        manager
        .artifacts_for_interaction(

            "interaction-1"
        )
    )

    assert len(artifacts) == 2


def test_distinguishes_repeated_interactions_on_same_object_and_action():

    artifact_store = (

        InMemoryResearchArtifactStore()
    )

    link_store = (

        InMemoryInteractionArtifactLinkStore()
    )

    manager = (

        InteractionArtifactCorrelationManager(

            link_store=link_store,

            artifact_store=(
                artifact_store
            ),
        )
    )

    first = ResearchArtifact(

        session_id="session-1",

        object_id="attention",

        artifact_type=(

            ResearchArtifactType
            .EXPLANATION
        ),

        action="explain",

        content="Explanation v1",
    )

    second = ResearchArtifact(

        session_id="session-1",

        object_id="attention",

        artifact_type=(

            ResearchArtifactType
            .EXPLANATION
        ),

        action="explain",

        content="Explanation v2",
    )

    artifact_store.save(first)

    artifact_store.save(second)

    manager.link(
        "interaction-1",
        first,
    )

    manager.link(
        "interaction-2",
        second,
    )

    resolved_first = (

        manager
        .primary_artifact_for_interaction(

            "interaction-1"
        )
    )

    resolved_second = (

        manager
        .primary_artifact_for_interaction(

            "interaction-2"
        )
    )

    assert (

        resolved_first.content

        == "Explanation v1"
    )

    assert (

        resolved_second.content

        == "Explanation v2"
    )
