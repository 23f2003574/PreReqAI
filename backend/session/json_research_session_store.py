from copy import deepcopy

from datetime import datetime

from pathlib import Path

from backend.storage import (
    AtomicJsonFile,
)

from .research_session_snapshot import (
    ResearchSessionSnapshot,
)

from .research_session_store import (
    ResearchSessionStore,
)


class JsonResearchSessionStore(
    ResearchSessionStore
):
    """
    Persists research session snapshots
    to a JSON file.
    """

    def __init__(

        self,

        path: str | Path,

    ):

        self.file = AtomicJsonFile(

            path,

            default_factory=dict,
        )

    def save(

        self,

        snapshot:
            ResearchSessionSnapshot,

    ) -> ResearchSessionSnapshot:

        snapshot.updated_at = (
            datetime.utcnow()
        )

        sessions = self.file.read()

        sessions[
            snapshot.session_id
        ] = snapshot.to_dict()

        self.file.write(
            sessions
        )

        return deepcopy(
            snapshot
        )

    def load(

        self,

        session_id: str,

    ) -> ResearchSessionSnapshot | None:

        sessions = self.file.read()

        data = sessions.get(
            session_id
        )

        if data is None:

            return None

        return (

            ResearchSessionSnapshot
            .from_dict(

                data
            )
        )

    def delete(

        self,

        session_id: str,

    ) -> bool:

        sessions = self.file.read()

        if session_id not in sessions:

            return False

        del sessions[
            session_id
        ]

        self.file.write(
            sessions
        )

        return True

    def list_sessions(

        self,

    ) -> list[
        ResearchSessionSnapshot
    ]:

        sessions = self.file.read()

        snapshots = [

            ResearchSessionSnapshot
            .from_dict(

                data
            )

            for data

            in sessions.values()
        ]

        return sorted(

            snapshots,

            key=lambda item:
                item.updated_at,

            reverse=True,
        )
