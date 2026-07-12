from datetime import datetime

from backend.session import (

    ResearchCheckpoint,

    ResearchCheckpointReason,
)


def test_checkpoint_round_trip_serialization():

    checkpoint = ResearchCheckpoint(

        session_id="session-1",

        reason=(

            ResearchCheckpointReason
            .ARTIFACT_CREATED
        ),

        snapshot_updated_at=(
            datetime.utcnow()
        ),

        metadata={

            "artifact_id":
                "artifact-1",
        },
    )

    restored = (

        ResearchCheckpoint
        .from_dict(

            checkpoint.to_dict()
        )
    )

    assert (

        restored.id

        == checkpoint.id
    )

    assert (

        restored.reason

        == checkpoint.reason
    )

    assert (

        restored.metadata

        == checkpoint.metadata
    )
