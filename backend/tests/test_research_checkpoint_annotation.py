from backend.session import (
    ResearchCheckpointAnnotation,
)


def test_checkpoint_annotation_round_trip():

    annotation = (

        ResearchCheckpointAnnotation(

            checkpoint_id=(
                "checkpoint-1"
            ),

            session_id=(
                "session-1"
            ),

            label=(
                "Best methodology state"
            ),

            note=(
                "Preserve this point."
            ),

            pinned=True,
        )
    )

    restored = (

        ResearchCheckpointAnnotation
        .from_dict(

            annotation.to_dict()
        )
    )

    assert (

        restored.checkpoint_id

        == "checkpoint-1"
    )

    assert (

        restored.label

        == "Best methodology state"
    )

    assert restored.pinned is True
