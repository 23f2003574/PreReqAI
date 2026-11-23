"""A bound on how many analyses one server runs at the same time.

Each upload starts a PDF worker process that may use up to PREREQAI_PARSE_MEMORY_MB of memory and a CPU for PREREQAI_PARSE_SECONDS, so an unbounded number of simultaneous uploads can exhaust the
machine whatever the per-file limits say. PREREQAI_MAX_CONCURRENT_ANALYSES sets the number allowed at once (default: the number of CPUs, at most 4, at least 1; a value that is not a positive whole
number is ignored). A request that finds every slot taken is not queued: it is refused at once with 503 and Retry-After, so a client can back off and no request waits holding a connection."""
import os
import threading

SLOTS_ENV = "PREREQAI_MAX_CONCURRENT_ANALYSES"
RETRY_AFTER_SECONDS = 5
_lock = threading.Lock()
_active = 0


def limit():
    """How many analyses may run at once under the current settings."""
    try:
        wanted = int((os.environ.get(SLOTS_ENV) or "").strip())
    except ValueError:
        wanted = 0
    return wanted if wanted >= 1 else max(1, min(4, os.cpu_count() or 1))


def try_acquire():
    """True when a slot was free and is now held (the caller must `release` it); False when every slot is taken."""
    global _active
    with _lock:
        if _active >= limit():
            return False
        _active += 1
        return True


def release():
    global _active
    with _lock:
        _active = max(0, _active - 1)


def active():
    with _lock:
        return _active
