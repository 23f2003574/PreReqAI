def add_note(error: BaseException, note: str) -> None:
    """`error.add_note(note)` (Python 3.11+); on 3.10, which this project supports, the same `__notes__` list is kept so
    callers and tests read one thing on every version (3.10's traceback just does not print it)."""
    if hasattr(error, "add_note"):
        error.add_note(note)
    else:
        error.__notes__ = [*getattr(error, "__notes__", []), note]
