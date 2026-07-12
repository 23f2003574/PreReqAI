from copy import deepcopy

from datetime import datetime

from .research_session_snapshot import (
    ResearchSessionSnapshot,
)

from .research_session_store import (
    ResearchSessionStore,
)


class InMemoryResearchSessionStore(
    ResearchSessionStore
):
    """
    Stores research session snapshots
    in memory.

    Primarily useful for testing,
    development, and temporary runtime
    persistence.
    """

    def __init__(self):

        self._sessions: dict[

            str,

            ResearchSessionSnapshot,

        ] = {}

    def save(

        self,

        snapshot:
            ResearchSessionSnapshot,

    ) -> ResearchSessionSnapshot:

        snapshot.updated_at = (
            datetime.utcnow()
        )

        stored = deepcopy(
            snapshot
        )

        self._sessions[

            snapshot.session_id

        ] = stored

        return deepcopy(
            stored
        )

    def load(

        self,

        session_id: str,

    ) -> ResearchSessionSnapshot | None:

        snapshot = self._sessions.get(
            session_id
        )

        if snapshot is None:

            return None

        return deepcopy(
            snapshot
        )

    def delete(

        self,

        session_id: str,

    ) -> bool:

        if (

            session_id

            not in self._sessions
        ):

            return False

        del self._sessions[
            session_id
        ]

        return True

    def list_sessions(

        self,

    ) -> list[
        ResearchSessionSnapshot
    ]:

        return [

            deepcopy(
                snapshot
            )

            for snapshot

            in sorted(

                self._sessions.values(),

                key=lambda item:
                    item.updated_at,

                reverse=True,
            )
        ]
