from dataclasses import dataclass
from datetime import datetime

RESTORED = "RESTORED"
STATUSES = frozenset({RESTORED})


@dataclass(frozen=True)
class LLMTransformationRollback:
    """An immutable, reasoned record of restoring one applied execution's
    original source (Commit #5's own atomic rollback()).

    status is always RESTORED -- rollback() either fully restores the
    execution's original source and records this, or raises before
    touching anything (see LLMTransformationRollbackService). reason is
    the caller's own account of why the rollback happened (typically a
    Commit #6 verification failure or a Commit #7 critical regression) and
    is always recorded, never inferred or discarded.
    """

    rollback_id: str
    execution_id: str
    reason: str
    status: str
    restored_at: datetime
