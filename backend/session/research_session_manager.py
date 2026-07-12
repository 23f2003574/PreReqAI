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

    ):

        self.store = store

        self.serializer = (

            serializer

            or ResearchSessionSerializer()
        )

    def save_workspace(

        self,

        session_id: str,

        workspace,

        paper_id: str | None = None,

        paper_title: str | None = None,

    ):

        snapshot = (

            self.serializer.serialize(

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
