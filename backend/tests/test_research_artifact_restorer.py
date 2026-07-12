from backend.session import (

    InMemoryResearchArtifactStore,

    ResearchArtifact,

    ResearchArtifactRestorer,

    ResearchArtifactType,
)

from frontend.src.workspace import (
    VisualResearchWorkspace,
)


def test_restores_artifact_into_workspace():

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

        action="explain",

        content=(

            "Attention allows a model "
            "to weigh relevant tokens."
        ),
    )

    store.save(
        artifact
    )

    restorer = (

        ResearchArtifactRestorer(

            store
        )
    )

    workspace = (
        VisualResearchWorkspace()
    )

    result = (

        restorer
        .restore_for_interaction(

            interaction_id=(
                "interaction-1"
            ),

            artifact_ids=[
                artifact.id
            ],

            workspace=workspace,
        )
    )

    assert result.restored is True

    assert (

        len(
            result.learning_content
        )

        == 1
    )

    assert (

        workspace.learning_content()
        .body

        == artifact.content
    )


def test_marks_learning_content_as_restored():

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

        action="explain",

        content="Explanation",
    )

    store.save(
        artifact
    )

    restorer = (

        ResearchArtifactRestorer(
            store
        )
    )

    workspace = (
        VisualResearchWorkspace()
    )

    result = (

        restorer
        .restore_for_interaction(

            interaction_id=(
                "interaction-1"
            ),

            artifact_ids=[
                artifact.id
            ],

            workspace=workspace,
        )
    )

    content = (

        result.learning_content[0]
    )

    assert (

        content.metadata[
            "restored"
        ]

        is True
    )

    assert (

        content.metadata[
            "artifact_id"
        ]

        == artifact.id
    )


def test_reports_missing_artifact():

    store = (
        InMemoryResearchArtifactStore()
    )

    restorer = (

        ResearchArtifactRestorer(
            store
        )
    )

    workspace = (
        VisualResearchWorkspace()
    )

    result = (

        restorer
        .restore_for_interaction(

            interaction_id=(
                "interaction-1"
            ),

            artifact_ids=[
                "missing-artifact"
            ],

            workspace=workspace,
        )
    )

    assert (

        result.restored

        is False
    )

    assert (

        result.missing_artifact_ids

        == [
            "missing-artifact"
        ]
    )


def test_does_not_duplicate_restored_artifact():

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

        action="explain",

        content="Explanation",
    )

    store.save(
        artifact
    )

    restorer = (

        ResearchArtifactRestorer(
            store
        )
    )

    workspace = (
        VisualResearchWorkspace()
    )

    for _ in range(2):

        restorer.restore_for_interaction(

            interaction_id=(
                "interaction-1"
            ),

            artifact_ids=[
                artifact.id
            ],

            workspace=workspace,
        )

    history = (

        workspace
        .workspace
        .learning_panel
        .content_history
    )

    matches = [

        content

        for content

        in history

        if (

            content.metadata.get(
                "artifact_id"
            )

            == artifact.id
        )
    ]

    assert len(matches) == 1
