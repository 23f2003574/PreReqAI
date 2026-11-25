"""A bound on how many analyses run at the same time across ALL server worker processes on this computer.

Each upload starts a PDF worker process that may use up to PREREQAI_PARSE_MEMORY_MB of memory and a CPU for PREREQAI_PARSE_SECONDS, so an unbounded number of simultaneous uploads can exhaust the
machine whatever the per-file limits say. PREREQAI_MAX_CONCURRENT_ANALYSES sets the number allowed at once (default: the number of CPUs, at most 4, at least 1; a value that is not a positive whole
number is ignored). A request that finds every slot taken is not queued: it is refused at once with 503 and Retry-After, so a client can back off and no request waits holding a connection.

Each slot is a small lock file (in PREREQAI_SLOTS_DIR, default a per-user `prereqai-slots-*` folder of the temporary directory) held with an exclusive non-blocking operating-system lock for as long as the analysis runs, so
the limit is shared by every worker (`--workers N` no longer allows N times the limit), taking the last slot is atomic (two processes cannot both get it) and the system frees a slot when its process dies, so a crashed
worker never keeps capacity. Where file locks are unavailable (Windows) the limit falls back to counting within this process."""
import os
import tempfile
import threading
from pathlib import Path

try:
    import fcntl
except ImportError:  # no POSIX file locks: count within this process only
    fcntl = None

SLOTS_ENV, DIR_ENV = "PREREQAI_MAX_CONCURRENT_ANALYSES", "PREREQAI_SLOTS_DIR"
RETRY_AFTER_SECONDS = 5
_lock = threading.Lock()
_active = 0  # the in-process count, used only without file locks
_held = []  # open slot files this process holds, one per running analysis


def limit():
    """How many analyses may run at once under the current settings."""
    try:
        wanted = int((os.environ.get(SLOTS_ENV) or "").strip())
    except ValueError:
        wanted = 0
    return wanted if wanted >= 1 else max(1, min(4, os.cpu_count() or 1))


def _directory():
    configured = (os.environ.get(DIR_ENV) or "").strip()
    owner = os.getuid() if hasattr(os, "getuid") else os.environ.get("USERNAME", "user")
    folder = Path(configured) if configured else Path(tempfile.gettempdir()) / f"prereqai-slots-{owner}"
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    return folder


def _take(number):
    """The open slot file `number` with its exclusive lock held, or None when another analysis (in any process) holds it."""
    handle = open(_directory() / f"slot-{number}.lock", "a+b")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return None
    return handle


def try_acquire():
    """True when a slot was free and is now held (the caller must `release` it); False when every slot is taken."""
    global _active
    with _lock:
        if fcntl is None:
            if _active >= limit():
                return False
            _active += 1
            return True
        for number in range(limit()):
            handle = _take(number)
            if handle is not None:
                _held.append(handle)
                return True
        return False


def release():
    global _active
    with _lock:
        if fcntl is None:
            _active = max(0, _active - 1)
        elif _held:
            _held.pop().close()  # closing the file releases its lock


def active():
    """How many slots are in use right now, by any process."""
    with _lock:
        if fcntl is None:
            return _active
        busy = 0
        for number in range(max(limit(), len(_held))):
            handle = _take(number)
            if handle is None:
                busy += 1
            else:
                handle.close()
        return busy
