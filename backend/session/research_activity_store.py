from abc import (
    ABC,
    abstractmethod,
)

from .research_activity_event import (
    ResearchActivityEvent,
)


class ResearchActivityStore(
    ABC,
):
    """
    Persistence boundary for immutable
    research activity events.
    """

    @abstractmethod
    def append(

        self,

        event:
            ResearchActivityEvent,

    ) -> None:

        raise NotImplementedError

    @abstractmethod
    def get(

        self,

        event_id: str,

    ) -> ResearchActivityEvent | None:

        raise NotImplementedError

    @abstractmethod
    def list_all(

        self,

    ) -> list[
        ResearchActivityEvent
    ]:

        raise NotImplementedError
