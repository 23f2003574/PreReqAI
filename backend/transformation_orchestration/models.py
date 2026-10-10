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
class LLMTransformationDecision:
    """The single, current, deterministic verdict for one orchestrated
    transformation, updated as it moves through transform() -> review() ->
    release()/rollback().

    execution_id is None only for a decision recorded before an execution
    ever existed -- an explicit approval rejection during transform().
    release_id is set only once release() has actually created one.
    Exactly one decision is tracked per execution_id at a time -- each
    stage replaces the previous verdict rather than appending to a list,
    so decision(execution_id) always reflects the transformation's most
    current, authoritative state.
    """

    decision_id: str
    execution_id: Optional[str]
    status: str
    release_id: Optional[str]
    reason: str
    created_at: datetime
