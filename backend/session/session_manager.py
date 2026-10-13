import os
import pickle
import time
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
    process only) so a restarted server still knows them. Saved sessions expire after
    PREREQAI_SESSION_MAX_AGE_DAYS days without activity (default 30; 0 keeps them forever): expired files are
    deleted when a new session is created and are treated as unknown if requested first.
    """

    DEFAULT_MAX_AGE_DAYS = 30.0

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

    @classmethod
    def _max_age_seconds(cls) -> float | None:
        """None: never expire. An unset, unreadable or negative setting falls back to the default."""

        try:

            days = float(os.environ.get("PREREQAI_SESSION_MAX_AGE_DAYS", cls.DEFAULT_MAX_AGE_DAYS))

        except ValueError:

            days = cls.DEFAULT_MAX_AGE_DAYS

        if days != days or days < 0:  # NaN or negative

            days = cls.DEFAULT_MAX_AGE_DAYS

        return days * 86400 if days > 0 else None

    @classmethod
    def _expired(cls, path: Path) -> bool:

        max_age = cls._max_age_seconds()

        try:

            return max_age is not None and time.time() - path.stat().st_mtime > max_age

        except OSError:

            return False

    def purge_expired(self) -> int:
        """Delete saved session files (and leftover temp files) past the expiry; returns how many were removed."""

        directory = os.environ.get("PREREQAI_SESSION_DIR")

        if not directory or not Path(directory).is_dir():

            return 0

        removed = 0

        for path in [*Path(directory).glob("*.session"), *Path(directory).glob("*.tmp")]:

            if self._expired(path):

                try:

                    path.unlink()

                    removed += 1

                except OSError:

                    pass

        return removed

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

        self.purge_expired()

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

            if self._expired(path):  # past its expiry: gone, even if no new session has triggered a purge yet

                path.unlink(missing_ok=True)

                return None

            try:

                session = pickle.loads(path.read_bytes())

            except Exception:  # unreadable or from an incompatible version: same as unknown

                return None

            if not isinstance(session, LearningSession):  # readable but not a session: same as unknown

                return None

            self.sessions[session_id] = session

        return session

    def delete(self, session_id: str) -> bool:
        """Forget a session: drop it from memory and delete its saved file. False when no such session existed."""

        known = self.get(session_id) is not None

        self.sessions.pop(session_id, None)

        path = self._path(session_id)

        if path is not None:

            try:

                path.unlink(missing_ok=True)

            except OSError:

                pass

        return known

    def list(self) -> list[LearningSession]:
        """Every known session: those in memory plus those only saved in PREREQAI_SESSION_DIR (restored on the way),
        newest first. Expired, unreadable and foreign files are skipped."""

        directory = os.environ.get("PREREQAI_SESSION_DIR")

        if directory and Path(directory).is_dir():

            for path in Path(directory).glob("*.session"):

                self.get(path.stem)  # loads (and caches) it when valid; does nothing for bad names

        # sessions saved by older versions lack created_at
        return sorted(self.sessions.values(), key=lambda session: getattr(session, "created_at", 0.0), reverse=True)
