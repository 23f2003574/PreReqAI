from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

# A plan whose refresh_actions reference a real, currently-existing source
# is actionable; one that is stale/unknown but has nothing concrete to act
# on (e.g. an "external" source, or no provenance at all) is not. Plain
# string vocabulary, the same convention as backend.llm.context_freshness's
# FRESH/STALE/UNKNOWN.
ACTIONABLE = "actionable"
UNRESOLVABLE = "unresolvable"

REFRESH_PLAN_STATUSES = (ACTIONABLE, UNRESOLVABLE)


@dataclass(frozen=True)
class LLMContextRefreshPlan:
    """An immutable, point-in-time proposal for refreshing one stale/unknown context.

    Built entirely from Commit #9's freshness check and Commit #6's
    provenance -- never applied here (no automatic refresh in this commit):
    plan() only records what could be done, preview() only shows what it
    would replace, and validate() only re-checks whether it still can be
    done. Nothing about the source context is ever overwritten.
    """

    context_id: str
    stale_sources: tuple
    refresh_actions: tuple
    reason: str
    status: str
    plan_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
