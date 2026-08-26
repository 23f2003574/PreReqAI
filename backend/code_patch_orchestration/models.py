from dataclasses import dataclass
from datetime import datetime
from typing import Optional

REJECTED = "REJECTED"
APPLIED = "APPLIED"
ROLLED_BACK = "ROLLED_BACK"
READY_FOR_RELEASE = "READY_FOR_RELEASE"
RELEASED = "RELEASED"
STATUSES = frozenset({REJECTED, APPLIED, ROLLED_BACK, READY_FOR_RELEASE, RELEASED})


@dataclass(frozen=True)
class LLMCodePatchDecision:
    """The single, current, deterministic verdict for one orchestrated patch,
    updated as it moves through apply() -> verify() -> release()/rollback().

    execution_id is None only for a decision recorded before an execution
    ever existed -- a validation rejection during apply(). release_candidate_id
    is set only once release() has actually created one (Commit #12).
    blocking_findings names exactly which check(s) rejected this patch --
    empty once (and only once) status is READY_FOR_RELEASE or RELEASED.
    Exactly one decision is tracked per execution_id at a time -- each
    stage replaces the previous verdict rather than appending to a list,
    so decision(execution_id) always reflects the patch's most current,
    authoritative state.
    """

    decision_id: str
    execution_id: Optional[str]
    status: str
    release_candidate_id: Optional[str]
    blocking_findings: list
    reason: str
    created_at: datetime
