from datetime import datetime

import pytest

from backend.session import (

    InMemoryResearchCheckpointAnnotationStore,

    InMemoryResearchCheckpointStore,

    ResearchCheckpoint,

    ResearchCheckpointAnnotationManager,

    ResearchCheckpointReason,
)


def create_manager_with_checkpoint():

    checkpoint_store = (

        InMemoryResearchCheckpointStore()
    )

    checkpoint = ResearchCheckpoint(

        session_id="session-1",

        reason=(

            ResearchCheckpointReason
            .MANUAL
        ),

        snapshot_updated_at=(
            datetime.utcnow()
        ),
    )

    checkpoint_store.save(
        checkpoint
    )

    manager = (

        ResearchCheckpointAnnotationManager(

            checkpoint_store=(
                checkpoint_store
            ),

            annotation_store=(

                InMemoryResearchCheckpointAnnotationStore()
            ),
        )
    )

    return (
        manager,
        checkpoint,
    )


def test_creates_checkpoint_annotation():

    manager, checkpoint = (

        create_manager_with_checkpoint()
    )

    annotation = manager.update(

        checkpoint.id,

        label=(
            "Important state"
        ),

        note=(
            "Before major rewrite"
        ),

        pinned=True,
    )

    assert (

        annotation.label

        == "Important state"
    )

    assert (

        annotation.note

        == "Before major rewrite"
    )

    assert annotation.pinned is True


def test_partial_annotation_update_preserves_other_fields():

    manager, checkpoint = (

        create_manager_with_checkpoint()
    )

    manager.update(

        checkpoint.id,

        label="Important state",

        note="Original note",

        pinned=True,
    )

    updated = manager.update(

        checkpoint.id,

        label="Renamed state",
    )

    assert (

        updated.label

        == "Renamed state"
    )

    assert (

        updated.note

        == "Original note"
    )

    assert updated.pinned is True


def test_can_explicitly_clear_checkpoint_label():

    manager, checkpoint = (

        create_manager_with_checkpoint()
    )

    manager.update(

        checkpoint.id,

        label="Temporary label",
    )

    updated = manager.update(

        checkpoint.id,

        label=None,
    )

    assert updated.label is None


def test_blank_checkpoint_label_becomes_none():

    manager, checkpoint = (

        create_manager_with_checkpoint()
    )

    annotation = manager.update(

        checkpoint.id,

        label="     ",
    )

    assert annotation.label is None


def test_update_with_no_arguments_changes_nothing():

    manager, checkpoint = (

        create_manager_with_checkpoint()
    )

    manager.update(

        checkpoint.id,

        label="Kept label",

        note="Kept note",

        pinned=True,
    )

    unchanged = manager.update(
        checkpoint.id
    )

    assert (

        unchanged.label

        == "Kept label"
    )

    assert (

        unchanged.note

        == "Kept note"
    )

    assert unchanged.pinned is True


def test_cannot_annotate_unknown_checkpoint():

    checkpoint_store = (

        InMemoryResearchCheckpointStore()
    )

    manager = (

        ResearchCheckpointAnnotationManager(

            checkpoint_store=(
                checkpoint_store
            ),

            annotation_store=(

                InMemoryResearchCheckpointAnnotationStore()
            ),
        )
    )

    with pytest.raises(

        ValueError,

        match=(
            "does not exist"
        ),
    ):

        manager.update(

            "missing-checkpoint",

            label="Impossible",
        )
