"""Portable cross-process file locking for PreReqAI's read-modify-write files (learner profiles, saved sessions, the analysis cache).

`locked(path)` holds an exclusive lock for the file at `path` for the duration of a `with` block: a thread lock (so threads of one process queue, and the same thread may nest the
block again) and, on top of it, an operating-system lock on a sibling `.<name>.lock` file, so other processes (several server workers, the CLI beside the server) queue too. The
lock is released when the block ends however it ends (an exception, an interrupt), and by the system if the process dies, so it cannot be left held. Waiting longer than
`timeout` seconds raises LockTimeout (an OSError) instead of blocking for ever. POSIX uses fcntl.flock; Windows uses msvcrt.locking, which this project's tests have not run
on (the continuous-integration jobs are Linux). The lock files do not clutter the data directories: they live in a per-user folder of the system temporary directory, named by a hash of the data file's absolute path (empty, safe to delete when nothing is running)."""
import contextlib
import hashlib
import os
import tempfile
import threading
import time
from pathlib import Path

try:
    import fcntl
except ImportError:  # Windows
    fcntl = None
    import msvcrt

DEFAULT_TIMEOUT = 30.0
_POLL = 0.01
_registry_guard = threading.Lock()
_thread_locks = {}  # lock file path -> [RLock, depth owned by the current holder, open file or None]


class LockTimeout(OSError):
    """The lock was not available within the timeout."""


def lock_path(path):
    """The lock file of the data file at `path`: in a private per-user folder of the temporary directory, named by the hash of the data file's absolute path."""
    owner = os.getuid() if hasattr(os, "getuid") else os.environ.get("USERNAME", "user")
    folder = Path(tempfile.gettempdir()) / f"prereqai-locks-{owner}"
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    return folder / (hashlib.sha256(str(Path(path).absolute()).encode("utf-8")).hexdigest()[:40] + ".lock")


def _try_os_lock(handle):
    """True when the exclusive operating-system lock was taken, False when another process holds it."""
    try:
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        else:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        return True
    except OSError:
        return False


def _release_os_lock(handle):
    try:
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        else:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    finally:
        handle.close()


@contextlib.contextmanager
def locked(path, timeout=DEFAULT_TIMEOUT):
    """Exclusive access to the file at `path` for this block, across threads and processes; nesting in one thread is fine."""
    name = str(lock_path(path))
    with _registry_guard:
        entry = _thread_locks.setdefault(name, [threading.RLock(), 0, None])
    deadline = time.monotonic() + timeout
    if not entry[0].acquire(timeout=timeout):
        raise LockTimeout(f"could not lock {path} within {timeout:g} seconds (another thread holds it)")
    try:
        if entry[1] == 0:  # the outermost entry of this thread takes the operating-system lock
            Path(name).parent.mkdir(parents=True, exist_ok=True)
            handle = open(name, "a+b")
            try:
                while not _try_os_lock(handle):
                    if time.monotonic() >= deadline:
                        raise LockTimeout(f"could not lock {path} within {timeout:g} seconds (another process holds it)")
                    time.sleep(_POLL)
            except BaseException:
                handle.close()
                raise
            entry[2] = handle
        entry[1] += 1
        try:
            yield
        finally:
            entry[1] -= 1
            if entry[1] == 0:
                handle, entry[2] = entry[2], None
                _release_os_lock(handle)
    finally:
        entry[0].release()
