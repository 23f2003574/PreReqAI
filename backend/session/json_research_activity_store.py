from pathlib import Path

from backend.storage import (
    AtomicJsonFile,
)

from .research_activity_event import (
    ResearchActivityEvent,
)

from .research_activity_store import (
    ResearchActivityStore,
)


def _default_data():

    return {
        "events": {},
    }


class JsonResearchActivityStore(
    ResearchActivityStore,
):
    """
    Persists immutable research activity
    events to JSON, in append order.
    """

    def __init__(

        self,

        path: str | Path,

    ):

        self.file = AtomicJsonFile(

            path,

            default_factory=(
                _default_data
            ),
        )

    def append(

        self,

        event,

    ):

        data = self.file.read()

        if event.id in data["events"]:

            raise ValueError(

                "Research activity event "
                "already exists: "
                f"{event.id}"
            )

        data["events"][
            event.id
        ] = event.to_dict()

        self.file.write(
            data
        )

    def get(

        self,

        event_id,

    ):

        data = self.file.read()

        raw = (

            data["events"].get(
                event_id
            )
        )

        if raw is None:

            return None

        return (

            ResearchActivityEvent
            .from_dict(

                raw
            )
        )

    def list_all(self):

        data = self.file.read()

        return [

            ResearchActivityEvent
            .from_dict(

                raw
            )

            for raw

            in data["events"].values()
        ]

    def export_state(self):

        return self.file.read()

    def restore_state(

        self,

        state,

    ) -> None:

        self.file.write(
            state
        )
