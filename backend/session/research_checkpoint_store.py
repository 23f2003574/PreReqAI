from abc import (
    ABC,
    abstractmethod,
)

from .research_checkpoint import (
    ResearchCheckpoint,
)


class ResearchCheckpointStore(ABC):
    """
    Defines persistence operations
    for research checkpoint history.
    """

    @abstractmethod
    def save(

        self,

        checkpoint:
            ResearchCheckpoint,

    ) -> ResearchCheckpoint:

        raise NotImplementedError

    @abstractmethod
    def get(

        self,

        checkpoint_id: str,

    ) -> ResearchCheckpoint | None:

        raise NotImplementedError

    @abstractmethod
    def list_for_session(

        self,

        session_id: str,

    ) -> list[
        ResearchCheckpoint
    ]:

        raise NotImplementedError

    @abstractmethod
    def latest_for_session(

        self,

        session_id: str,

    ) -> ResearchCheckpoint | None:

        raise NotImplementedError

    @abstractmethod
    def delete(

        self,

        checkpoint_id: str,

    ) -> bool:

        raise NotImplementedError

    @abstractmethod
    def list_all(

        self,

    ) -> list[
        ResearchCheckpoint
    ]:

        raise NotImplementedError

    @abstractmethod
    def export_state(
        self,
    ):

        raise NotImplementedError

    @abstractmethod
    def restore_state(

        self,

        state,

    ) -> None:

        raise NotImplementedError
