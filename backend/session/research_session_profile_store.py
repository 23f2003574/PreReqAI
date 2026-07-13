from abc import (
    ABC,
    abstractmethod,
)

from .research_session_profile import (
    ResearchSessionProfile,
)


class ResearchSessionProfileStore(
    ABC
):
    """
    Defines persistence operations
    for mutable research session
    profiles.
    """

    @abstractmethod
    def save(

        self,

        profile:
            ResearchSessionProfile,

    ) -> ResearchSessionProfile:

        raise NotImplementedError

    @abstractmethod
    def get(

        self,

        session_id: str,

    ) -> ResearchSessionProfile | None:

        raise NotImplementedError

    @abstractmethod
    def list_all(

        self,

    ) -> list[
        ResearchSessionProfile
    ]:

        raise NotImplementedError
