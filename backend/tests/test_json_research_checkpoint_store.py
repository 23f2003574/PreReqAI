from datetime import datetime

from backend.session import (

    JsonResearchCheckpointStore,

    ResearchCheckpoint,

    ResearchCheckpointReason,
)


def test_checkpoint_survives_store_recreation(

    tmp_path,

):

    path = (

        tmp_path

        / "checkpoints.json"
    )

    first_store = (

        JsonResearchCheckpointStore(

            path
        )
    )

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

    first_store.save(
        checkpoint
    )

    second_store = (

        JsonResearchCheckpointStore(

            path
        )
    )

    restored = (

        second_store.get(

            checkpoint.id
        )
    )

    assert restored is not None

    assert (

        restored.session_id

        == "session-1"
    )

    assert (

        restored.reason

        == (
            ResearchCheckpointReason
            .ARTIFACT_CREATED
        )
    )

    assert (

        restored.metadata[
            "artifact_id"
        ]

        == "artifact-1"
    )


def test_lists_checkpoints_in_creation_order(

    tmp_path,

):

    path = (

        tmp_path

        / "checkpoints.json"
    )

    store = (

        JsonResearchCheckpointStore(

            path
        )
    )

    first = ResearchCheckpoint(

        session_id="session-1",

        reason=(

            ResearchCheckpointReason
            .WORKFLOW_PROGRESS
        ),

        snapshot_updated_at=(
            datetime.utcnow()
        ),
    )

    second = ResearchCheckpoint(

        session_id="session-1",

        reason=(

            ResearchCheckpointReason
            .ARTIFACT_CREATED
        ),

        snapshot_updated_at=(
            datetime.utcnow()
        ),
    )

    store.save(first)

    store.save(second)

    checkpoints = (

        store.list_for_session(

            "session-1"
        )
    )

    assert (

        [
            checkpoint.id

            for checkpoint

            in checkpoints
        ]

        == [

            first.id,

            second.id,
        ]
    )


def test_checkpoint_store_isolates_sessions(

    tmp_path,

):

    path = (

        tmp_path

        / "checkpoints.json"
    )

    store = (

        JsonResearchCheckpointStore(

            path
        )
    )

    first = ResearchCheckpoint(

        session_id="session-1",

        reason=(

            ResearchCheckpointReason
            .WORKFLOW_PROGRESS
        ),

        snapshot_updated_at=(
            datetime.utcnow()
        ),
    )

    second = ResearchCheckpoint(

        session_id="session-2",

        reason=(

            ResearchCheckpointReason
            .SECTION_CHANGED
        ),

        snapshot_updated_at=(
            datetime.utcnow()
        ),
    )

    store.save(first)

    store.save(second)

    session_one = (

        store.list_for_session(

            "session-1"
        )
    )

    assert len(session_one) == 1

    assert (

        session_one[0].id

        == first.id
    )
