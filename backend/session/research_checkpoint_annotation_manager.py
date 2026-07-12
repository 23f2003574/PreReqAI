from datetime import datetime

from .research_checkpoint_annotation import (
    ResearchCheckpointAnnotation,
)

from .unset import (
    UNSET,
)


class ResearchCheckpointAnnotationManager:
    """
    Coordinates mutable human-authored
    checkpoint annotations.
    """

    def __init__(

        self,

        checkpoint_store,

        annotation_store,

    ):

        self.checkpoint_store = (
            checkpoint_store
        )

        self.annotation_store = (
            annotation_store
        )

    def update(

        self,

        checkpoint_id: str,

        label=UNSET,

        note=UNSET,

        pinned=UNSET,

    ):

        label = self._normalize_text(
            label
        )

        note = self._normalize_text(
            note
        )

        checkpoint = (

            self.checkpoint_store
            .get(

                checkpoint_id
            )
        )

        if checkpoint is None:

            raise ValueError(

                "Research checkpoint "
                "does not exist: "
                f"{checkpoint_id}"
            )

        existing = (

            self.annotation_store
            .get(

                checkpoint_id
            )
        )

        now = datetime.utcnow()

        if existing is None:

            annotation = (

                ResearchCheckpointAnnotation(

                    checkpoint_id=(
                        checkpoint.id
                    ),

                    session_id=(
                        checkpoint.session_id
                    ),

                    label=(

                        None

                        if label is UNSET

                        else label
                    ),

                    note=(

                        None

                        if note is UNSET

                        else note
                    ),

                    pinned=(

                        False

                        if pinned is UNSET

                        else bool(
                            pinned
                        )
                    ),

                    created_at=now,

                    updated_at=now,
                )
            )

        else:

            annotation = existing

            if label is not UNSET:

                annotation.label = (
                    label
                )

            if note is not UNSET:

                annotation.note = (
                    note
                )

            if pinned is not UNSET:

                annotation.pinned = (
                    bool(
                        pinned
                    )
                )

            annotation.updated_at = now

        return (

            self.annotation_store
            .save(

                annotation
            )
        )

    def get(

        self,

        checkpoint_id: str,

    ):

        return (

            self.annotation_store
            .get(

                checkpoint_id
            )
        )

    def remove(

        self,

        checkpoint_id: str,

    ):

        return (

            self.annotation_store
            .delete(

                checkpoint_id
            )
        )

    def for_session(

        self,

        session_id: str,

    ):

        return (

            self.annotation_store
            .list_for_session(

                session_id
            )
        )

    def pinned_for_session(

        self,

        session_id: str,

    ):

        return [

            annotation

            for annotation

            in self.for_session(
                session_id
            )

            if annotation.pinned
        ]

    @staticmethod
    def _normalize_text(

        value,

    ):

        if value is UNSET:

            return UNSET

        if value is None:

            return None

        normalized = (
            value.strip()
        )

        return (

            normalized

            if normalized

            else None
        )
