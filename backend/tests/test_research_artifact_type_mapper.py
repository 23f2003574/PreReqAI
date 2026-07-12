from backend.session import (

    ResearchArtifactType,

    ResearchArtifactTypeMapper,
)


def test_maps_action_to_artifact_type():

    artifact_type = (

        ResearchArtifactTypeMapper
        .from_action(

            "visualize"
        )
    )

    assert (

        artifact_type

        == (
            ResearchArtifactType
            .VISUALIZATION
        )
    )


def test_unknown_action_maps_to_other():

    artifact_type = (

        ResearchArtifactTypeMapper
        .from_action(

            "unknown-action"
        )
    )

    assert (

        artifact_type

        == (
            ResearchArtifactType
            .OTHER
        )
    )
