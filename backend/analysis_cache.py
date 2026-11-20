"""The analysis cache: a completed analysis of a PDF, found again by the SHA-256 of its bytes.

What is cached is the paper's analysis only (the Paper and its report, before any learner's known or studied concepts, hours per day, profile, quiz
results or session exist), keyed by the file's hash, PIPELINE_VERSION (raise it whenever ingestion, parsing, detection or reporting output changes) and
the settings that change the analysis text (PREREQAI_OCR_LANGS). Every request gets its own deep copy, so one learner's changes can never reach
another's, and a changed file or version is simply a different key. Identical files analysed at the same time are analysed once: the others wait for
the first and take its result, and if the first fails they analyse for themselves. Results with scanned pages left unread by an OCR budget are not
cached (they are partial). With PREREQAI_ANALYSIS_CACHE_DIR the entries are also kept on disk as JSON in the session format (nothing is unpickled), written to
a temporary file and moved into place, so a crash leaves no partial entry; an entry that cannot be read is removed and treated as a miss."""
import hashlib
import json
import os
import threading
from collections import OrderedDict
from copy import deepcopy
from pathlib import Path

from backend.filelock import locked

PIPELINE_VERSION = "2026-11-20.1"
MAX_ENTRIES = 16
_CHUNK = 1024 * 1024


def file_key(path):
    """The cache key of a file (SHA-256 of its bytes with the pipeline version and settings), or None when it cannot be read."""
    digest = hashlib.sha256()
    try:
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(_CHUNK), b""):
                digest.update(chunk)
    except OSError:
        return None
    settings = os.environ.get("PREREQAI_OCR_LANGS", "").strip().lower()
    return f"{digest.hexdigest()}-{hashlib.sha256((PIPELINE_VERSION + '|' + settings).encode()).hexdigest()[:12]}"


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
        except Exception:
            pass  # a cache that cannot be written is only a missed speed-up

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
            lock = self._locks.setdefault(key, threading.Lock())
        with lock:
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
