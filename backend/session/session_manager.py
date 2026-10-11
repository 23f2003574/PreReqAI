import os
import pickle
from pathlib import Path
from uuid import UUID

from backend.models import Paper

from .learning_session import (
    LearningSession,
)


class SessionManager:
    """
    Manages active learning sessions. Sessions live in memory; when the PREREQAI_SESSION_DIR environment
    variable names a directory they are also saved there (one local file per session, written by this
    process only) so a restarted server still knows them.
    """

    def __init__(self):

        self.sessions = {}

    @staticmethod
    def _path(session_id: str) -> Path | None:

        directory = os.environ.get("PREREQAI_SESSION_DIR")

        try:  # the id is client input: only a canonical UUID may become a file name

            valid = str(UUID(session_id)) == session_id

        except (ValueError, AttributeError, TypeError):

            valid = False

        return Path(directory) / f"{session_id}.session" if directory and valid else None

    def save(self, session: LearningSession) -> None:
        """Write the session to PREREQAI_SESSION_DIR (no-op when unset or the write fails: memory stays authoritative)."""

        path = self._path(session.session_id)

        if path is None:

            return

        try:

            path.parent.mkdir(parents=True, exist_ok=True)

            temp = path.with_suffix(".tmp")

            temp.write_bytes(pickle.dumps(session))

            temp.replace(path)

        except Exception:

            pass

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

        self.save(session)

        return session

    def get(
        self,
        session_id: str,
    ) -> LearningSession | None:

        session = self.sessions.get(
            session_id,
        )

        path = self._path(session_id) if session is None else None

        if path is not None and path.is_file():

            try:

                session = pickle.loads(path.read_bytes())

            except Exception:  # unreadable or from an incompatible version: same as unknown

                return None

            self.sessions[session_id] = session

        return session
