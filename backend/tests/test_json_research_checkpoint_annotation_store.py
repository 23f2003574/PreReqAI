from backend.session import (

    JsonResearchCheckpointAnnotationStore,

    ResearchCheckpointAnnotation,
)


def test_annotation_survives_store_recreation(

    tmp_path,

):

    path = (

        tmp_path

        / "checkpoint_annotations.json"
    )

    first_store = (

        JsonResearchCheckpointAnnotationStore(

            path
        )
    )

    annotation = (

        ResearchCheckpointAnnotation(

            checkpoint_id=(
                "checkpoint-1"
            ),

            session_id=(
                "session-1"
            ),

            label=(
                "Important state"
            ),

            note=(
                "Restore if needed."
            ),

            pinned=True,
        )
    )

    first_store.save(
        annotation
    )

    second_store = (

        JsonResearchCheckpointAnnotationStore(

            path
        )
    )

    restored = (

        second_store.get(

            "checkpoint-1"
        )
    )

    assert restored is not None

    assert (

        restored.label

        == "Important state"
    )

    assert restored.pinned is True


def test_deletes_annotation(

    tmp_path,

):

    path = (

        tmp_path

        / "checkpoint_annotations.json"
    )

    store = (

        JsonResearchCheckpointAnnotationStore(

            path
        )
    )

    annotation = (

        ResearchCheckpointAnnotation(

            checkpoint_id=(
                "checkpoint-1"
            ),

            session_id=(
                "session-1"
            ),
        )
    )

    store.save(
        annotation
    )

    deleted = store.delete(
        "checkpoint-1"
    )

    assert deleted is True

    assert (

        store.get(
            "checkpoint-1"
        )

        is None
    )
