from abc import (
    ABC,
    abstractmethod,
)

from .research_session_version import (
    ResearchSessionVersion,
)


class ResearchSessionVersionStore(ABC):
    """
    Defines persistence operations
    for immutable historical research
    session versions.
    """

    @abstractmethod
    def save(

        self,

        version:
            ResearchSessionVersion,

    ) -> ResearchSessionVersion:

        raise NotImplementedError

    @abstractmethod
    def get(

        self,

        version_id: str,

    ) -> ResearchSessionVersion | None:

        raise NotImplementedError

    @abstractmethod
    def list_for_session(

        self,

        session_id: str,

    ) -> list[
        ResearchSessionVersion
    ]:

        raise NotImplementedError

    @abstractmethod
    def latest_for_session(

        self,

        session_id: str,

    ) -> ResearchSessionVersion | None:

        raise NotImplementedError

    @abstractmethod
    def delete(

        self,

        version_id: str,

    ) -> bool:

        raise NotImplementedError
