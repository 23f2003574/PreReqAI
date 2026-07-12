from abc import (
    ABC,
    abstractmethod,
)

from .research_artifact import (
    ResearchArtifact,
)


class ResearchArtifactStore(ABC):
    """
    Defines persistence operations
    for generated research artifacts.
    """

    @abstractmethod
    def save(

        self,

        artifact:
            ResearchArtifact,

    ) -> ResearchArtifact:

        raise NotImplementedError

    @abstractmethod
    def get(

        self,

        artifact_id: str,

    ) -> ResearchArtifact | None:

        raise NotImplementedError

    @abstractmethod
    def delete(

        self,

        artifact_id: str,

    ) -> bool:

        raise NotImplementedError

    @abstractmethod
    def list_for_session(

        self,

        session_id: str,

    ) -> list[
        ResearchArtifact
    ]:

        raise NotImplementedError

    @abstractmethod
    def list_for_object(

        self,

        session_id: str,

        object_id: str,

    ) -> list[
        ResearchArtifact
    ]:

        raise NotImplementedError
