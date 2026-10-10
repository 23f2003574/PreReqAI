from abc import (
    ABC,
    abstractmethod,
)

from .research_checkpoint_annotation import (
    ResearchCheckpointAnnotation,
)


class ResearchCheckpointAnnotationStore(
    ABC
):
    """
    Defines persistence operations
    for mutable human-authored
    checkpoint annotations.
    """

    @abstractmethod
    def save(

        self,

        annotation:
            ResearchCheckpointAnnotation,

    ) -> ResearchCheckpointAnnotation:

        raise NotImplementedError

    @abstractmethod
    def get(

        self,

        checkpoint_id: str,

    ) -> ResearchCheckpointAnnotation | None:

        raise NotImplementedError

    @abstractmethod
    def list_for_session(

        self,

        session_id: str,

    ) -> list[
        ResearchCheckpointAnnotation
    ]:

        raise NotImplementedError

    @abstractmethod
    def delete(

        self,

        checkpoint_id: str,

    ) -> bool:

        raise NotImplementedError
