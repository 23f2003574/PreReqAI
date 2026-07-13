from copy import (
    deepcopy,
)

from .research_activity_store import (
    ResearchActivityStore,
)


class InMemoryResearchActivityStore(
    ResearchActivityStore,
):
    """
    Stores immutable research activity
    events in memory, in append order.
    """

    def __init__(self):

        self._events = []

        self._events_by_id = {}

    def append(

        self,

        event,

    ):

        if event.id in self._events_by_id:

            raise ValueError(

                "Research activity event "
                "already exists: "
                f"{event.id}"
            )

        stored = deepcopy(
            event
        )

        self._events.append(
            stored
        )

        self._events_by_id[
            stored.id
        ] = stored

    def get(

        self,

        event_id,

    ):

        event = (

            self._events_by_id.get(

                event_id
            )
        )

        return (

            deepcopy(
                event
            )

            if event is not None

            else None
        )

    def list_all(self):

        return [

            deepcopy(
                event
            )

            for event

            in self._events
        ]
