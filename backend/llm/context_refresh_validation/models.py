from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

# Plain string finding-code vocabulary, the same convention as
# backend.llm.context_freshness's FRESH/STALE/UNKNOWN and
# backend.llm.context_refresh_execution's SUCCEEDED/PARTIAL/FAILED.
MISSING_PROVENANCE = "missing_provenance"
MALFORMED_CONTENT = "malformed_content"
SOURCE_VERSION_MISMATCH = "source_version_mismatch"
STALE_REFRESH = "stale_refresh"
INCOMPLETE_REFRESH = "incomplete_refresh"
UNVERIFIABLE_FRESHNESS = "unverifiable_freshness"

FINDING_CODES = (
    MISSING_PROVENANCE,
    MALFORMED_CONTENT,
    SOURCE_VERSION_MISMATCH,
    STALE_REFRESH,
    INCOMPLETE_REFRESH,
    UNVERIFIABLE_FRESHNESS,
)

# Every code above is blocking except UNVERIFIABLE_FRESHNESS, which is
# informational: the repository simply has nothing wired to confirm
# freshness one way or the other (e.g. an "external" source), which is not
# itself evidence that the refresh is wrong.
BLOCKING_FINDING_CODES = frozenset(FINDING_CODES) - {UNVERIFIABLE_FRESHNESS}


@dataclass(frozen=True)
class LLMContextRefreshValidation:
    """The outcome of re-checking a completed Commit #11 execution's result.

    Read-only: computing this never creates a version, touches provenance,
    or activates/rolls back anything -- it only reads through Commits
    #1/#2/#6/#9/#11. valid is False whenever findings contains at least one
    blocking entry; non-blocking findings are informational only.
    """

    execution_id: str
    valid: bool
    findings: tuple
    validation_id: str = field(default_factory=lambda: str(uuid4()))
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
