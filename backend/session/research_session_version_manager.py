from copy import deepcopy

from .research_session_version import (
    ResearchSessionVersion,
)

from .research_session_version_store import (
    ResearchSessionVersionStore,
)


class ResearchSessionVersionManager:
    """
    Coordinates immutable historical
    versions of research session
    snapshots.
    """

    def __init__(

        self,

        store:
            ResearchSessionVersionStore,

    ):

        self.store = store

    def create(

        self,

        snapshot,

        metadata: dict | None = None,

    ):

        version = ResearchSessionVersion(

            session_id=(
                snapshot.session_id
            ),

            snapshot=deepcopy(
                snapshot
            ),

            metadata=(

                metadata

                if metadata is not None

                else {}
            ),
        )

        return self.store.save(
            version
        )

    def get(

        self,

        version_id: str,

    ):

        return self.store.get(
            version_id
        )

    def for_session(

        self,

        session_id: str,

    ):

        return (

            self.store
            .list_for_session(

                session_id
            )
        )

    def latest(

        self,

        session_id: str,

    ):

        return (

            self.store
            .latest_for_session(

                session_id
            )
        )

    def delete(

        self,

        version_id: str,

    ):

        return self.store.delete(
            version_id
        )
