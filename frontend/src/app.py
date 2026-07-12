from frontend.src.workspace import (
    create_visual_research_workspace,
)

from backend.session import (
    InMemoryResearchSessionStore,
    ResearchSessionManager,
)


class PreReqAIApplication:
    """
    Application-level entry point
    for the visual PreReqAI experience.
    """

    def __init__(self):

        self.workspace = (
            create_visual_research_workspace()
        )

        self.session_store = (
            InMemoryResearchSessionStore()
        )

        self.session_manager = (
            ResearchSessionManager(

                self.session_store
            )
        )

    def save_research_session(

        self,

        session_id: str,

        paper_id: str | None = None,

        paper_title: str | None = None,

    ):

        return (

            self.session_manager
            .save_workspace(

                session_id=session_id,

                workspace=self.workspace,

                paper_id=paper_id,

                paper_title=paper_title,
            )
        )

    def get_research_session(

        self,

        session_id: str,

    ):

        return (

            self.session_manager
            .load_session(

                session_id
            )
        )

    def research_sessions(self):

        return (

            self.session_manager
            .list_sessions()
        )
