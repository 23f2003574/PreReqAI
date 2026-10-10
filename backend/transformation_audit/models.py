from dataclasses import dataclass
from datetime import datetime

APPLIED = "APPLIED"
VERIFIED = "VERIFIED"
VERIFICATION_FAILED = "VERIFICATION_FAILED"
ROLLED_BACK = "ROLLED_BACK"
STATUSES = frozenset({APPLIED, VERIFIED, VERIFICATION_FAILED, ROLLED_BACK})


@dataclass(frozen=True)
class LLMTransformationAudit:
    """One append-only snapshot of a transformation's full lifecycle, from
    plan through diff, approval, execution, and (once available)
    verification or rollback.

    Never mutated or replaced in place -- record() always appends a new
    entry rather than editing an old one, so history(notebook_id) is a
    genuine audit trail across every point the lifecycle was captured.
    reviewer is the diff's own recorded approver (Commit #4), redacted if
    it looks like a secret or credential rather than a human identifier.
    status reflects the most current fact known at record() time: APPLIED
    until a verification or rollback exists, then VERIFIED /
    VERIFICATION_FAILED, and finally ROLLED_BACK once the execution itself
    has been rolled back (Commit #5), which always takes precedence.
    """

    audit_id: str
    plan_id: str
    diff_id: str
    execution_id: str
    reviewer: str
    status: str
    created_at: datetime
