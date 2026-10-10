from dataclasses import dataclass, field
from datetime import datetime, timezone

# Plain string status vocabulary, the same convention as
# backend.llm.tool_execution's STATUSES / backend.llm.tool_audit's
# PLANNED/STATUSES, rather than a new Enum type.
FRESH = "fresh"
STALE = "stale"
UNKNOWN = "unknown"

FRESHNESS_STATUSES = (FRESH, STALE, UNKNOWN)


@dataclass
class LLMContextFreshness:
    """The outcome of comparing a context (or snapshot) against its current source.

    subject_id is the context_id for check()/stale()/refresh_candidates(),
    or the snapshot_id for check_snapshot() -- the id of whatever was
    actually evaluated, not necessarily the id of the source it was
    compared against.
    """

    subject_id: str
    status: str
    reason: str
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
