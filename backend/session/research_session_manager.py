from .research_session_serializer import (
    ResearchSessionSerializer,
)

from .research_session_store import (
    ResearchSessionStore,
)


class ResearchSessionManager:
    """
    Coordinates serialization and
    persistence of visual research
    sessions.
    """

    def __init__(

        self,

        store: ResearchSessionStore,

        serializer=None,

        restorer=None,

    ):

        self.store = store

        self.serializer = (

            serializer

            or ResearchSessionSerializer()
        )

        self.restorer = restorer

    def snapshot_workspace(

        self,

        session_id: str,

        workspace,

        paper_id: str | None = None,

        paper_title: str | None = None,

    ):

        return (

            self.serializer.serialize(

                session_id=session_id,

                workspace=workspace,

                paper_id=paper_id,

                paper_title=paper_title,
            )
        )

    def save_workspace(

        self,

        session_id: str,

        workspace,

        paper_id: str | None = None,

        paper_title: str | None = None,

    ):

        snapshot = (

            self.snapshot_workspace(

                session_id=session_id,

                workspace=workspace,

                paper_id=paper_id,

                paper_title=paper_title,
            )
        )

        return self.store.save(
            snapshot
        )

    def load_session(

        self,

        session_id: str,

    ):

        return self.store.load(
            session_id
        )

    def delete_session(

        self,

        session_id: str,

    ):

        return self.store.delete(
            session_id
        )

    def list_sessions(self):

        return self.store.list_sessions()

    def restore_workspace(

        self,

        session_id: str,

        workspace,

    ):

        if self.restorer is None:

            raise ValueError(

                "A research session "
                "restorer is required."
            )

        snapshot = self.load_session(

            session_id
        )

        if snapshot is None:

            raise ValueError(

                "Research session "
                "could not be found."
            )

        return self.restorer.restore(

            snapshot,

            workspace,
        )
