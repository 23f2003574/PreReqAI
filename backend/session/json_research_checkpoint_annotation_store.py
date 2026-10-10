from pathlib import Path

from backend.storage import (
    AtomicJsonFile,
)

from .research_checkpoint_annotation import (
    ResearchCheckpointAnnotation,
)

from .research_checkpoint_annotation_store import (
    ResearchCheckpointAnnotationStore,
)


class JsonResearchCheckpointAnnotationStore(
    ResearchCheckpointAnnotationStore
):
    """
    Persists human-authored checkpoint
    annotations to a JSON file.
    """

    def __init__(

        self,

        path: str | Path,

    ):

        self.file = AtomicJsonFile(

            path,

            default_factory=dict,
        )

    def save(

        self,

        annotation:
            ResearchCheckpointAnnotation,

    ) -> ResearchCheckpointAnnotation:

        annotations = (
            self.file.read()
        )

        annotations[
            annotation.checkpoint_id
        ] = annotation.to_dict()

        self.file.write(
            annotations
        )

        return (

            ResearchCheckpointAnnotation
            .from_dict(

                annotation.to_dict()
            )
        )

    def get(

        self,

        checkpoint_id: str,

    ) -> ResearchCheckpointAnnotation | None:

        annotations = (
            self.file.read()
        )

        data = annotations.get(
            checkpoint_id
        )

        if data is None:

            return None

        return (

            ResearchCheckpointAnnotation
            .from_dict(

                data
            )
        )

    def list_for_session(

        self,

        session_id: str,

    ) -> list[
        ResearchCheckpointAnnotation
    ]:

        annotations = (
            self.file.read()
        )

        matching = []

        for data in annotations.values():

            annotation = (

                ResearchCheckpointAnnotation
                .from_dict(

                    data
                )
            )

            if (

                annotation.session_id

                == session_id
            ):

                matching.append(
                    annotation
                )

        return sorted(

            matching,

            key=lambda item:
                item.updated_at,
        )

    def delete(

        self,

        checkpoint_id: str,

    ) -> bool:

        annotations = (
            self.file.read()
        )

        if (

            checkpoint_id

            not in annotations
        ):

            return False

        del annotations[
            checkpoint_id
        ]

        self.file.write(
            annotations
        )

        return True
