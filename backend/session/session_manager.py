from backend.models import Paper

from .learning_session import (
    LearningSession,
)


class SessionManager:
    """
    Manages active learning sessions.
    """

    def __init__(self):

        self.sessions = {}

    def create(
        self,
        paper_title: str,
        report: dict | None = None,
        paper: Paper | None = None,
    ) -> LearningSession:

        session = LearningSession(

            paper_title=paper_title,

            report=report or {},

            paper=paper,
        )

        self.sessions[
            session.session_id
        ] = session

        return session

    def get(
        self,
        session_id: str,
    ) -> LearningSession | None:

        return self.sessions.get(
            session_id,
        )
