"""The analysis cache: a completed analysis of a PDF, found again by the SHA-256 of its bytes.

What is cached is the paper's analysis only (the Paper and its report, before any learner's known or studied concepts, hours per day, profile, quiz
results or session exist), keyed by the file's hash, PIPELINE_VERSION (raise it for a change the fingerprint cannot see, such as data outside the listed source files) and
the settings that change the analysis text (PREREQAI_OCR_LANGS), and a fingerprint of the source files that produce an analysis (`source_fingerprint`), so an entry made by earlier code is never served
after a change to ingestion, parsing, detection, prerequisites or reporting, whether or not anyone remembered to raise PIPELINE_VERSION. Every request gets its own deep copy, so one learner's changes can never reach
another's, and a changed file or version is simply a different key. Identical files analysed at the same time are analysed once: the others wait for
the first and take its result, and if the first fails they analyse for themselves. Results with scanned pages left unread by an OCR budget are not
cached (they are partial). With PREREQAI_ANALYSIS_CACHE_DIR the entries are also kept on disk as JSON in the session format (nothing is unpickled), written to
a temporary file and moved into place, so a crash leaves no partial entry; an entry that cannot be read is removed and treated as a miss."""
import hashlib
import json
import os
import threading
import time
from collections import OrderedDict
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

from backend.filelock import locked

PIPELINE_VERSION = "2026-11-23.1"
MAX_ENTRIES = 16
DEFAULT_DISK_ENTRIES = 200
STALE_TEMP_SECONDS = 3600
_CHUNK = 1024 * 1024


SOURCE_PACKAGES = ("ingestion", "parsing", "concepts", "prerequisites", "pipeline", "models", "reporting", "resources", "platform", "graph", "serialization")
SOURCE_MODULES = ("evidence.py", "extraction_confidence.py", "math_plan.py", "sentences.py", "custom_concepts.py", "filelock.py")
_SOURCE_SUFFIXES = (".py", ".json")


def source_fingerprint(root=None):
    """A hash of the files that decide what an analysis contains: every .py and .json file in SOURCE_PACKAGES of `root` (default: the backend package) and the SOURCE_MODULES beside them, by
    relative path and bytes (caches and tests excluded). A file added, removed or edited changes it; an unrelated package does not. Over-invalidating is safe (one slower analysis), so the list is generous."""
    base = Path(root) if root is not None else Path(__file__).resolve().parent
    paths = [base / name for name in SOURCE_MODULES]
    for package in SOURCE_PACKAGES:
        paths.extend(p for p in (base / package).rglob("*") if p.suffix in _SOURCE_SUFFIXES and "__pycache__" not in p.parts)
    digest = hashlib.sha256()
    for path in sorted(p for p in paths if p.is_file()):
        digest.update(path.relative_to(base).as_posix().encode() + b"\0")
        try:
            digest.update(path.read_bytes())
        except OSError:
            digest.update(b"unreadable")
        digest.update(b"\0")
    return digest.hexdigest()[:16]


_fingerprint = lru_cache(maxsize=1)(source_fingerprint)


def file_key(path):
    """The cache key of a file (SHA-256 of its bytes with the pipeline version and settings), or None when it cannot be read."""
    digest = hashlib.sha256()
    try:
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(_CHUNK), b""):
                digest.update(chunk)
    except OSError:
        return None
    from backend.custom_concepts import load as custom_load

    custom = "|".join(sorted(t.lower() for c in custom_load()[0] for t in (c["name"], *c["aliases"])))  # confirming a custom concept must change what is detected in a paper seen before
    settings = os.environ.get("PREREQAI_OCR_LANGS", "").strip().lower() + "|" + custom
    return f"{digest.hexdigest()}-{hashlib.sha256((PIPELINE_VERSION + '|' + _fingerprint() + '|' + settings).encode()).hexdigest()[:12]}"


class AnalysisCache:
    def __init__(self, max_entries=MAX_ENTRIES):
        self.max_entries, self._entries, self._locks = max_entries, OrderedDict(), {}
        self._guard = threading.Lock()
        self.hits = self.misses = 0

    def clear(self):
        with self._guard:
            self._entries.clear()
            self.hits = self.misses = 0

    @staticmethod
    def directory():
        value = os.environ.get("PREREQAI_ANALYSIS_CACHE_DIR", "").strip()
        return Path(value).expanduser() if value else None

    def _read_disk(self, key):
        directory = self.directory()
        target = directory / f"{key}.json" if directory else None
        if target is None or not target.exists():
            return None
        try:
            from backend.session import session_codec

            data = json.loads(target.read_bytes())
            os.utime(target)  # read: the most recently used entry is the last to be pruned
            return {"paper": session_codec.decode(data["paper"]), "report": data["report"], "timings": data["timings"]}
        except Exception:
            with locked(target):
                target.unlink(missing_ok=True)  # damaged or from another version: gone, and the analysis runs again
            return None

    def _write_disk(self, key, entry):
        directory = self.directory()
        if directory is None:
            return
        try:
            from backend.session import session_codec

            directory.mkdir(parents=True, exist_ok=True)
            temp = directory / f".{key}.{os.getpid()}.{threading.get_ident()}.tmp"
            try:
                temp.write_text(json.dumps({"paper": session_codec.encode(entry["paper"]), "report": entry["report"], "timings": entry["timings"]},
                                           ensure_ascii=False, allow_nan=False), encoding="utf-8")
                with locked(directory / f"{key}.json"):  # processes filling the same entry take turns; the swap is atomic
                    os.replace(temp, directory / f"{key}.json")
            finally:
                temp.unlink(missing_ok=True)
            self.prune_disk(directory)
        except Exception:
            pass  # a cache that cannot be written is only a missed speed-up

    @staticmethod
    def disk_limit():
        """How many entries the disk cache keeps: PREREQAI_ANALYSIS_CACHE_MAX_ENTRIES (a whole number of at least 1), else DEFAULT_DISK_ENTRIES."""
        try:
            value = int(os.environ.get("PREREQAI_ANALYSIS_CACHE_MAX_ENTRIES", "").strip() or DEFAULT_DISK_ENTRIES)
        except ValueError:
            return DEFAULT_DISK_ENTRIES
        return value if value >= 1 else DEFAULT_DISK_ENTRIES

    def prune_disk(self, directory=None, limit=None, now=None):
        """Keep the disk cache within `limit` entries by removing the least recently used ones (an entry's modification time is refreshed when it is read), and remove temporary files that a crashed
        writer left behind (older than STALE_TEMP_SECONDS). Returns the names removed. The entry just written is the newest, so it is never the one removed."""
        directory = directory or self.directory()
        if directory is None or not directory.is_dir():
            return []
        limit, moment, removed = limit or self.disk_limit(), now if now is not None else time.time(), []
        entries = []
        for path in directory.iterdir():
            try:
                age = moment - path.stat().st_mtime
            except OSError:
                continue
            if path.name.startswith(".") and path.name.endswith(".tmp"):
                if age > STALE_TEMP_SECONDS:
                    path.unlink(missing_ok=True)
                    removed.append(path.name)
            elif path.suffix == ".json":
                entries.append((path.stat().st_mtime, path.name, path))
        for _, name, path in sorted(entries)[:max(0, len(entries) - limit)]:
            with locked(path):
                path.unlink(missing_ok=True)
            removed.append(name)
        return removed

    def _get(self, key):
        with self._guard:
            entry = self._entries.get(key)
            if entry is not None:
                self._entries.move_to_end(key)
        if entry is None and (entry := self._read_disk(key)) is not None:
            self._remember(key, entry)
        return deepcopy(entry) if entry is not None else None

    def _remember(self, key, entry):
        with self._guard:
            self._entries[key] = entry
            while len(self._entries) > self.max_entries:
                self._entries.popitem(last=False)

    def fetch(self, key, produce, should_cancel=None):
        """(entry, hit): the cached {"paper", "report", "timings"} for `key` (a private copy) or the result of `produce()` (stored first, then returned as a
        private copy). `should_cancel` (optional) is asked before a hit is returned. `produce` returns that dict, or one with "partial": True, which is returned but never stored. Calls for one key run one at a time."""
        if key is None:
            return produce(), False
        with self._guard:
            holder = self._locks.setdefault(key, [threading.Lock(), 0])  # [lock, callers using it]: dropped when the last caller leaves, so the table never outgrows the analyses in progress
            holder[1] += 1
        try:
            with holder[0]:
                return self._fetch_locked(key, produce, should_cancel)
        finally:
            with self._guard:
                holder[1] -= 1
                if holder[1] == 0 and self._locks.get(key) is holder:
                    del self._locks[key]

    def _fetch_locked(self, key, produce, should_cancel):
        cached = self._get(key)
        if cached is not None:
            if should_cancel is not None and should_cancel():  # a run already cancelled or past its time limit stops here, as it would at its first stage
                from backend.pipeline.research_paper_pipeline import PipelineCancelled

                raise PipelineCancelled("analysis cancelled")
            with self._guard:
                self.hits += 1
            return cached, True
        with self._guard:
            self.misses += 1
        entry = produce()
        if not entry.get("partial"):
            stored = {name: deepcopy(entry[name]) for name in ("paper", "report", "timings")}
            self._remember(key, stored)
            self._write_disk(key, stored)
        return entry, False


analysis_cache = AnalysisCache()
