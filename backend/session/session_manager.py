import os
import io
import logging
import pickle
import copy
import dataclasses
import threading

from backend.filelock import locked
import time
from pathlib import Path
from uuid import UUID

from . import session_codec, session_merge

from backend.models import Paper

from .learning_session import (
    LearningSession,
)


_log = logging.getLogger("prereqai.session")


class _SessionUnpickler(pickle.Unpickler):
    """Loads a saved session, resolving only classes defined in this project. A session file is the project's own dataclasses and plain
    containers, so anything else a file asks for (os.system, builtins.eval...) is refused instead of run: PREREQAI_SESSION_DIR may hold
    files this process did not write, and an unrestricted pickle.loads would execute them. A refused file reads as unreadable."""

    def find_class(self, module, name):
        found = super().find_class(module, name)
        if (module == "backend" or module.startswith("backend.")) and isinstance(found, type):
            return found
        raise pickle.UnpicklingError(f"refused to load {module}.{name} from a saved session")


def _fill_new_fields(root) -> bool:
    """Give every dataclass object reachable from `root` the fields that were added to its class after the file was written (an
    unpickled object restores only the attributes the file held, and a field with a default factory is not a class attribute, so reading
    it later raised AttributeError). Each gets its declared default. False when a missing field has no default: the file cannot be upgraded."""
    seen, pending = set(), [root]
    while pending:
        item = pending.pop()
        if id(item) in seen:
            continue
        seen.add(id(item))
        if dataclasses.is_dataclass(item) and not isinstance(item, type):
            for field in dataclasses.fields(item):
                if field.name in item.__dict__:
                    continue
                if field.default is not dataclasses.MISSING:
                    item.__dict__[field.name] = copy.copy(field.default)
                elif field.default_factory is not dataclasses.MISSING:
                    item.__dict__[field.name] = field.default_factory()
                else:
                    return False
            pending.extend(item.__dict__.values())
        elif isinstance(item, (list, tuple, set)):
            pending.extend(item)
        elif isinstance(item, dict):
            pending.extend(item.values())
    return True


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
    # Format of the saved files. 1: written before versions existed (no `schema_version`). 2: stamped on every save. 3: adds the quiz attempts. 4: a JSON envelope (see session_codec) instead of a pickle. 5: adds page numbers to paragraphs and sections and how a heading was recognised (a version 4 file is read as it is and gets those fields' defaults, page None, on load); the only format written now is the current one; files of versions 1-3 are pickles, read
    # only through the restricted unpickler and rewritten as version 4 when they are loaded. A file is upgraded on
    # load by giving objects the fields added since it was written (`_fill_new_fields`), which covers every change that only adds fields
    # with defaults; a change that renames, removes or retypes a field must bump this number and add its own step to `_migrate`. A file
    # from a newer version, or one that cannot be upgraded, reads as unreadable (404 "Session could not be restored"), never as a
    # session that fails later with an AttributeError.
    SCHEMA_VERSION = 5

    MAX_SESSIONS_IN_MEMORY = 500

    # Creating a session sweeps expired files from the session directory, which lists and stats every saved file;
    # the sweep runs at most this often, as an expired file is already skipped or removed whenever it is read or listed.
    PURGE_INTERVAL_SECONDS = 60

    def __init__(self):

        self._bases: dict[str, dict] = {}  # per session: the mergeable facts as last read or written (see session_merge)

        self.last_conflicts: list[str] = []

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

        self._signatures = {}  # session_id -> (mtime_ns, size, inode) of its file as this worker last read or wrote it, to notice another worker's save

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

            with save_lock, locked(path):  # one writer at a time across threads and processes

                path.parent.mkdir(parents=True, exist_ok=True)

                session.schema_version = self.SCHEMA_VERSION

                self._merge_with_saved(session, path)

                temp.write_bytes(session_codec.dumps(session, self.SCHEMA_VERSION))

                with temp.open("rb+") as written:  # on disk before the swap: a power loss must not leave an empty file under the real name

                    written.flush()

                    os.fsync(written.fileno())

                temp.replace(path)

                self._sync_directory(path.parent)

            self.last_save_ok = True

            with self._lock:

                self._unsaved.discard(session.session_id)

                self._bases[session.session_id] = session_merge.facts(session)

                self._signatures[session.session_id] = self._signature(path)

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

    def _merge_with_saved(self, session: LearningSession, path: Path) -> None:
        """Called under the file lock just before a write: when another worker saved this session since this one last read or wrote it (the file's version is
        higher), merge that worker's changes into `session` instead of overwriting them, then stamp the next version. A conflict that cannot be merged keeps this
        worker's value and is kept in `last_conflicts`. A file that is missing, unreadable (read again a few times) or from another session is simply replaced."""
        saved = None
        for attempt in range(3):
            if not path.is_file():
                break
            saved, _ = self._read_file(path)
            if saved is not None:
                break
            time.sleep(0.05 * (attempt + 1))
        base = self._bases.get(session.session_id)
        if saved is not None and base is not None and saved.version > session.version:
            conflicts = session_merge.merge(session, saved, base)
            if conflicts:
                self.last_conflicts = conflicts
                _log.warning("session %s: conflicting changes from two workers: %s", session.session_id, "; ".join(conflicts))
        session.version = max(session.version, saved.version if saved is not None else 0) + 1

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

            session, legacy = self._read_file(path)

            if session is None:

                return None

            with self._lock:

                # Another thread may have restored this id while this one was reading the file: keep the first object so
                # every request works on (and saves) the same session instead of each on its own copy.
                session = self.sessions.setdefault(session_id, session)

                self._bases[session_id] = session_merge.facts(session)

                self._signatures[session_id] = self._signature(path)

            if legacy:

                self._rewrite_as_json(session)

        elif session is not None:

            self._refresh_from_disk(session)

        if session is not None:

            with self._lock:

                self._last_used[session_id] = time.time()

            self._evict_oldest()  # restoring saved sessions one by one must not grow memory past the cap either

        return session

    @staticmethod
    def _signature(path: Path):
        try:
            info = path.stat()
        except OSError:
            return None
        return (info.st_mtime_ns, info.st_size, info.st_ino)

    def _refresh_from_disk(self, session: LearningSession) -> None:
        """A session held in memory is served as it is unless its file changed since this worker last read or wrote it, which means another worker saved it: that worker's changes are then merged into the
        held object (the same three-way merge a save uses, so this worker's own unsaved changes are kept) and the file's version is adopted, so a reader sees the other worker's progress without having to save first.
        Costs one `stat` per read; a file that is missing, unreadable or older than this worker's copy changes nothing."""
        path = self._path(session.session_id)
        if path is None:
            return
        signature = self._signature(path)
        if signature is None or signature == self._signatures.get(session.session_id):
            return
        saved, _ = self._read_file(path)
        if saved is None:  # being replaced or unreadable: try again on the next read
            return
        with self._lock:
            base = self._bases.get(session.session_id)
            if base is not None and saved.version > session.version:
                conflicts = session_merge.merge(session, saved, base)
                if conflicts:
                    self.last_conflicts = conflicts
                    _log.warning("session %s: conflicting changes from two workers: %s", session.session_id, "; ".join(conflicts))
                session.version = saved.version
                self._bases[session.session_id] = session_merge.facts(session)
            self._signatures[session.session_id] = signature

    def _rewrite_as_json(self, session: LearningSession) -> None:
        """Replace an older pickle file by the JSON one, but only after the JSON is shown to hold the same session (it is read back and written out
        again identically); otherwise the old file stays as it is, and the session keeps working from memory."""
        try:
            first = session_codec.dumps(session, self.SCHEMA_VERSION)
            _, again = session_codec.loads(first)
            if session_codec.dumps(again, self.SCHEMA_VERSION) != first:
                raise ValueError("the JSON does not reproduce the session")
        except Exception as error:
            _log.warning("saved session %s could not be converted to JSON, so its old file is kept: %s", session.session_id, error)
            return
        self.save(session)

    @staticmethod
    def _sync_directory(directory: Path) -> None:
        """Make the rename itself durable (best effort: not every platform can open a directory)."""
        try:
            handle = os.open(directory, os.O_RDONLY)
        except OSError:
            return
        try:
            os.fsync(handle)
        except OSError:
            pass
        finally:
            os.close(handle)

    @staticmethod
    def _read(path: Path) -> LearningSession | None:
        """The session saved in `path`; None when it is unreadable, from an incompatible version, not a session, or saved under another session's id."""
        return SessionManager._read_file(path)[0]

    @staticmethod
    def _read_file(path: Path):
        """(session or None, legacy): the session in `path` and whether the file is an older pickle (to be rewritten as JSON). A file that cannot be
        used reads as None and the reason is logged, never raised."""

        try:

            raw = path.read_bytes()

            legacy = raw.lstrip()[:1] != b"{"

            if legacy:  # versions 1-3 were pickles; only the restricted unpickler may read one, and only to migrate it

                session = _SessionUnpickler(io.BytesIO(raw)).load()

                version = getattr(session, "schema_version", 1)

            else:

                version, session = session_codec.loads(raw)

                session.schema_version = version

        except Exception as error:

            _log.warning("saved session %s is unreadable: %s", path.name, error)

            return None, False

        # A file renamed or copied under another id must not load as that id: the copy would answer for one id while
        # saving over the file of the session it really is.
        if not isinstance(session, LearningSession) or session.session_id != path.stem:

            _log.warning("saved session %s is unreadable: it holds another session", path.name)

            return None, False

        if not SessionManager._migrate(session, legacy):

            _log.warning("saved session %s is unreadable: unsupported version %r or fields that cannot be restored", path.name, version)

            return None, False

        SessionManager._reconcile_known_and_studied(session)

        return session, legacy

    @classmethod
    def _migrate(cls, session: LearningSession, legacy: bool = False) -> bool:
        """Bring a loaded session to the current format; False when it is from a version this one cannot read or cannot be upgraded. Pickle
        files are versions 1-3 only (none was ever written as 4); a JSON file is the current version (a newer one is unreadable)."""
        version = session.schema_version

        if isinstance(version, bool) or not isinstance(version, int):

            return False

        if not (1 <= version <= 3 if legacy else 4 <= version <= cls.SCHEMA_VERSION):

            return False

        # Fields added to a model after a file was written are filled on every load, whatever version the file claims: a field added without
        # a version bump (MissingPrerequisite.sections, added while the schema was still 3) left such files without the attribute, and the
        # next report rebuild failed with an AttributeError. Attributes of the file that the model no longer has are left in place.
        if not _fill_new_fields(session):

            return False

        session.schema_version = cls.SCHEMA_VERSION

        return True

    @staticmethod
    def _reconcile_known_and_studied(session: LearningSession) -> None:
        """A saved session (older version, hand-edited file) that lists a concept both as studied and as already known is made
        consistent the way marking it known does: it leaves the plan's progress and is remembered in `studied_while_known`,
        so un-marking known gives the study progress back. A consistent session is left untouched."""

        paper = session.paper

        if paper is None or not getattr(paper, "study_progress", None):

            return

        try:

            from backend.platform import platform
            from backend.platform.prereqai_platform import KNOWN_REASON

            known = {item.concept.casefold() for item in paper.missing_prerequisites if item.reason == KNOWN_REASON}

            clash = [item.concept for item in paper.study_progress if item.concept.casefold() in known and item.completed]

            if not clash:

                return

            paper.studied_while_known = [*getattr(paper, "studied_while_known", []), *clash]

            paper.study_progress = [item for item in paper.study_progress if item.concept not in clash]

            platform._refresh_progress(paper, session.report)

        except Exception:  # the file stays readable as saved: repairing is best effort

            pass

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

            self._bases.pop(session_id, None)

            self._last_used.pop(session_id, None)  # a deleted session must not leave bookkeeping behind in a long-lived server

        path = self._path(session_id)

        if path is not None:

            self._summaries.pop(path, None)

        if not known and path is not None and path.is_file():  # an unreadable saved file: removing it is a real delete

            known = True

        if path is not None:

            try:

                with locked(path):

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
            "progress": SessionManager._progress(session),
            "quiz_attempts": len(getattr(session, "quiz_attempts", None) or []),
        }

    @staticmethod
    def _progress(session) -> dict:
        """The planned study steps finished so far, for the history view: {completed, total, percent}."""
        steps = getattr(getattr(session, "paper", None), "study_progress", None) or []
        done = sum(1 for step in steps if getattr(step, "completed", False))
        return {"completed": done, "total": len(steps), "percent": round(100 * done / len(steps)) if steps else 0}

    def unreadable_ids(self) -> "list[str]":
        """Saved sessions whose file cannot be read (corrupt or from another version), sorted: the history lists them so they can be removed.
        Only files already examined by summaries() are known, so call summaries() first."""
        with self._lock:
            return sorted(path.stem for path, cached in self._summaries.items() if cached[1] is None and path.exists())

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
