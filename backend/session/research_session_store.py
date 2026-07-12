from abc import (
    ABC,
    abstractmethod,
)

from .research_session_snapshot import (
    ResearchSessionSnapshot,
)


class ResearchSessionStore(ABC):
    """
    Defines persistence operations
    for research session snapshots.
    """

    @abstractmethod
    def save(

        self,

        snapshot:
            ResearchSessionSnapshot,

    ) -> ResearchSessionSnapshot:

        raise NotImplementedError

    @abstractmethod
    def load(

        self,

        session_id: str,

    ) -> ResearchSessionSnapshot | None:

        raise NotImplementedError

    @abstractmethod
    def delete(

        self,

        session_id: str,

    ) -> bool:

        raise NotImplementedError

    @abstractmethod
    def list_sessions(

        self,

    ) -> list[
        ResearchSessionSnapshot
    ]:

        raise NotImplementedError
