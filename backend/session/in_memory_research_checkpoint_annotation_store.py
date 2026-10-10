from copy import deepcopy

from .research_checkpoint_annotation import (
    ResearchCheckpointAnnotation,
)

from .research_checkpoint_annotation_store import (
    ResearchCheckpointAnnotationStore,
)


class InMemoryResearchCheckpointAnnotationStore(
    ResearchCheckpointAnnotationStore
):
    """
    Stores checkpoint annotations
    in memory.
    """

    def __init__(self):

        self._annotations: dict[

            str,

            ResearchCheckpointAnnotation,

        ] = {}

    def save(

        self,

        annotation:
            ResearchCheckpointAnnotation,

    ) -> ResearchCheckpointAnnotation:

        stored = deepcopy(
            annotation
        )

        self._annotations[
            annotation.checkpoint_id
        ] = stored

        return deepcopy(
            stored
        )

    def get(

        self,

        checkpoint_id: str,

    ) -> ResearchCheckpointAnnotation | None:

        annotation = (

            self._annotations.get(

                checkpoint_id
            )
        )

        if annotation is None:

            return None

        return deepcopy(
            annotation
        )

    def list_for_session(

        self,

        session_id: str,

    ) -> list[
        ResearchCheckpointAnnotation
    ]:

        annotations = [

            annotation

            for annotation

            in self._annotations.values()

            if (

                annotation.session_id

                == session_id
            )
        ]

        return [

            deepcopy(
                annotation
            )

            for annotation

            in sorted(

                annotations,

                key=lambda item:
                    item.updated_at,
            )
        ]

    def delete(

        self,

        checkpoint_id: str,

    ) -> bool:

        if (

            checkpoint_id

            not in self._annotations
        ):

            return False

        del self._annotations[
            checkpoint_id
        ]

        return True
