from datetime import datetime

from backend.session import (

    InMemoryResearchCheckpointStore,

    ResearchCheckpoint,

    ResearchCheckpointReason,
)


def test_stores_checkpoint_history():

    store = (

        InMemoryResearchCheckpointStore()
    )

    checkpoint = ResearchCheckpoint(

        session_id="session-1",

        reason=(

            ResearchCheckpointReason
            .WORKFLOW_PROGRESS
        ),

        snapshot_updated_at=(
            datetime.utcnow()
        ),
    )

    store.save(
        checkpoint
    )

    checkpoints = (

        store.list_for_session(

            "session-1"
        )
    )

    assert len(checkpoints) == 1

    assert (

        checkpoints[0].id

        == checkpoint.id
    )


def test_get_and_delete_checkpoint():

    store = (

        InMemoryResearchCheckpointStore()
    )

    checkpoint = ResearchCheckpoint(

        session_id="session-1",

        reason=(

            ResearchCheckpointReason
            .WORKFLOW_PROGRESS
        ),

        snapshot_updated_at=(
            datetime.utcnow()
        ),
    )

    store.save(
        checkpoint
    )

    fetched = store.get(
        checkpoint.id
    )

    assert fetched is not None

    deleted = store.delete(
        checkpoint.id
    )

    assert deleted is True

    assert (

        store.get(
            checkpoint.id
        )

        is None
    )
