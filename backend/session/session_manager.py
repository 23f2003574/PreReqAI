import os
import pickle
import threading
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

    # A long-running server must not hold every analysed paper forever: past this many sessions in memory the
    # oldest are dropped from memory (saved ones can still be restored from PREREQAI_SESSION_DIR on request).
    MAX_SESSIONS_IN_MEMORY = 500

    # Creating a session sweeps expired files from the session directory, which lists and stats every saved file;
    # the sweep runs at most this often, as an expired file is already skipped or removed whenever it is read or listed.
    PURGE_INTERVAL_SECONDS = 60

    def __init__(self):

        self.sessions = {}

        # Requests run on worker threads: a listing iterating self.sessions while another request creates, restores,
        # evicts or deletes a session raised "dictionary keys changed during iteration". Every change to the table and
        # every iteration over it (as a snapshot) holds this lock.
        self._lock = threading.RLock()

        self.last_save_ok = True

        self._unsaved = set()  # ids whose latest save failed: memory holds progress the file lacks, so eviction must keep them

        self._save_locks = {}  # session_id -> lock: saves of one session run one at a time (see save)

        self._last_purge = float("-inf")

        self._summaries = {}  # saved-only session path -> ((mtime_ns, size), summary), so a listing re-reads only changed files

        self._last_used = {}  # session_id -> time of the latest create/get, so eviction drops the idlest session

    @staticmethod
    def _directory() -> str | None:
        """PREREQAI_SESSION_DIR with a leading ~ expanded (env files, systemd and Docker pass it unexpanded,
        which would otherwise create a directory literally named "~" in the working directory); None when unset or blank."""

        value = os.environ.get("PREREQAI_SESSION_DIR", "").strip()

        return os.path.expanduser(value) if value else None

    @staticmethod
    def _path(session_id: str) -> Path | None:

        directory = SessionManager._directory()

        try:  # the id is client input: only a canonical UUID may become a file name

            valid = str(UUID(session_id)) == session_id

        except (ValueError, AttributeError, TypeError):

            valid = False

        return Path(directory) / f"{session_id}.session" if directory and valid else None

    @classmethod
    def max_age_misconfiguration(cls) -> str | None:
        """A warning when PREREQAI_SESSION_DIR is in use and PREREQAI_SESSION_MAX_AGE_DAYS is set to something unusable (not a
        number, NaN or negative), so the default expiry applies instead; None when saving is off, or the setting is unset,
        blank or valid. A typo such as "7d" would otherwise quietly keep sessions for the default days, not the intended 7."""

        value = os.environ.get("PREREQAI_SESSION_MAX_AGE_DAYS", "").strip()

        if not value or cls._directory() is None:

            return None

        try:

            days = float(value)

        except ValueError:

            days = float("nan")

        if days != days or days < 0:

            return (f"PREREQAI_SESSION_MAX_AGE_DAYS={value!r} is not a number of days (0 keeps sessions forever), "
                    f"so the default of {cls.DEFAULT_MAX_AGE_DAYS:g} days applies.")

        return None

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

        directory = SessionManager._directory()

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

    def save(self, session: LearningSession) -> bool:
        """Write the session to PREREQAI_SESSION_DIR (no-op when unset or the write fails: memory stays authoritative).
        Returns False only when saving was configured but failed; `last_save_ok` keeps the latest result."""

        path = self._path(session.session_id)

        if path is None:

            self.last_save_ok = True

            return True

        # one temp file per writer: requests run in threads, and two saves of the same session sharing a temp file
        # truncated each other or lost the swap, reporting a failed save (and a lost restart) that never happened
        temp = path.with_name(f"{path.stem}.{os.getpid()}.{threading.get_ident()}.tmp")

        with self._lock:

            save_lock = self._save_locks.setdefault(session.session_id, threading.Lock())

        # Two saves of one session must not interleave: one that pickled an older state could otherwise replace the file
        # after a later save wrote the newer state, losing that update. Snapshot and swap happen under the session's lock.
        try:

            with save_lock:

                path.parent.mkdir(parents=True, exist_ok=True)

                temp.write_bytes(pickle.dumps(session))

                temp.replace(path)

            self.last_save_ok = True

            with self._lock:

                self._unsaved.discard(session.session_id)

        except BaseException as exc:  # an interrupt (Ctrl-C, SystemExit) must not leave its temp file behind either

            try:  # a half-written temp file (disk full) must not keep eating the space the next attempt needs

                temp.unlink(missing_ok=True)

            except OSError:

                pass

            if not isinstance(exc, Exception):  # the interrupt still propagates; only real failures become a failed save

                raise

            self.last_save_ok = False

            with self._lock:

                self._unsaved.add(session.session_id)

        return self.last_save_ok

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

        with self._lock:

            self.sessions[
                session.session_id
            ] = session

            self._last_used[session.session_id] = time.time()

        if time.time() - self._last_purge >= self.PURGE_INTERVAL_SECONDS:

            self._last_purge = time.time()

            self.purge_expired()

        self.save(session)

        self._evict_oldest()

        return session

    def _evict_oldest(self) -> None:

        with self._lock:

            excess = len(self.sessions) - self.MAX_SESSIONS_IN_MEMORY

            if excess > 0:

                oldest = sorted(
                    (item for item in self.sessions.values() if item.session_id not in self._unsaved),
                    key=lambda item: self._last_used.get(item.session_id, getattr(item, "created_at", 0.0)),
                )[:excess]

                for old in oldest:

                    self.sessions.pop(old.session_id, None)

                    self._last_used.pop(old.session_id, None)

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

            session = self._read(path)

            if session is None:

                return None

            with self._lock:

                # Another thread may have restored this id while this one was reading the file: keep the first object so
                # every request works on (and saves) the same session instead of each on its own copy.
                session = self.sessions.setdefault(session_id, session)

        if session is not None:

            with self._lock:

                self._last_used[session_id] = time.time()

            self._evict_oldest()  # restoring saved sessions one by one must not grow memory past the cap either

        return session

    @staticmethod
    def _read(path: Path) -> LearningSession | None:
        """The session saved in `path`; None when it is unreadable, from an incompatible version, not a session, or saved under another session's id."""

        try:

            session = pickle.loads(path.read_bytes())

        except Exception:

            return None

        # A file renamed or copied under another id must not load as that id: the copy would answer for one id while
        # saving over the file of the session it really is.
        if not isinstance(session, LearningSession) or session.session_id != path.stem:

            return None

        return session

    def is_unreadable(self, session_id: str) -> bool:
        """True when a saved file exists for this id but cannot be loaded (corrupt or from another version)."""

        path = self._path(session_id)

        return path is not None and path.is_file() and self.get(session_id) is None

    def delete(self, session_id: str) -> bool:
        """Forget a session: drop it from memory and delete its saved file. False when no such session existed."""

        known = self.get(session_id) is not None

        with self._lock:

            self.sessions.pop(session_id, None)

            self._save_locks.pop(session_id, None)

            self._unsaved.discard(session_id)

            self._last_used.pop(session_id, None)  # a deleted session must not leave bookkeeping behind in a long-lived server

        path = self._path(session_id)

        if path is not None:

            self._summaries.pop(path, None)

        if not known and path is not None and path.is_file():  # an unreadable saved file: removing it is a real delete

            known = True

        if path is not None:

            try:

                path.unlink(missing_ok=True)

            except OSError:

                pass

        return known

    def list(self) -> list[LearningSession]:
        """Every known session: those in memory plus those only saved in PREREQAI_SESSION_DIR (restored on the way),
        newest first. Expired, unreadable and foreign files are skipped."""

        directory = SessionManager._directory()

        with self._lock:

            found = dict(self.sessions)

        if directory and Path(directory).is_dir():

            for path in Path(directory).glob("*.session"):

                # Saved-only sessions are read for the listing but not cached: restoring every saved file into
                # memory would bypass MAX_SESSIONS_IN_MEMORY (a request for one session still restores it).
                if path.stem not in found and self._path(path.stem) is not None and not self._expired(path):

                    saved = self._read(path)

                    if saved is not None:

                        found[path.stem] = saved

        # sessions saved by older versions lack created_at
        # equal timestamps (coarse clocks) are ordered by id, not by dict/directory-listing order
        return sorted(found.values(), key=lambda session: (getattr(session, "created_at", 0.0), session.session_id), reverse=True)

    @staticmethod
    def _summary(session: LearningSession) -> dict:

        return {
            "session_id": session.session_id,
            "paper_title": session.paper_title,
            "created_at": getattr(session, "created_at", None),
            "readiness": (session.report.get("readiness") or {}).get("status"),
        }

    def summaries(self) -> "list[dict]":
        """What GET /api/session shows for every known session, newest first (the same sessions as `list`). A saved-only
        session is unpickled once and remembered while its file is unchanged: unpickling a whole paper per listing
        made the listing cost grow with every saved file's size."""

        directory = SessionManager._directory()

        with self._lock:

            snapshot = list(self.sessions.items())

        found = {session_id: self._summary(session) for session_id, session in snapshot}

        if directory and Path(directory).is_dir():

            for path in Path(directory).glob("*.session"):

                if path.stem in found or self._path(path.stem) is None or self._expired(path):

                    continue

                try:

                    info = path.stat()

                except OSError:

                    continue

                stamp = (info.st_mtime_ns, info.st_size)

                cached = self._summaries.get(path)

                if cached is None or cached[0] != stamp:

                    saved = self._read(path)

                    cached = (stamp, self._summary(saved) if saved is not None else None)

                    self._summaries[path] = cached

                if cached[1] is not None:

                    found[path.stem] = cached[1]

        for path in [path for path in self._summaries if not path.exists()]:  # deleted or purged files do not linger

            del self._summaries[path]

        return sorted(found.values(), key=lambda item: (item["created_at"] or 0.0, item["session_id"]), reverse=True)
