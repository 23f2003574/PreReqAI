from dataclasses import dataclass
from datetime import datetime

VERIFICATION = "VERIFICATION"
REGRESSION = "REGRESSION"
SECURITY = "SECURITY"
COMPATIBILITY = "COMPATIBILITY"
QUALITY = "QUALITY"
GATE_TYPES = frozenset({VERIFICATION, REGRESSION, SECURITY, COMPATIBILITY, QUALITY})

PASSED = "PASSED"
FAILED = "FAILED"
STATUSES = frozenset({PASSED, FAILED})


@dataclass(frozen=True)
class LLMCodePatchGate:
    """One release gate's deterministic evaluation for an applied Commit #5 execution.

    findings is a list of {"category", "message", "blocking"} dicts --
    status is FAILED whenever any of them is blocking, PASSED otherwise.
    Evaluating a gate only ever reads already-computed state (Commit #6
    verification, Commit #7 regression, Commit #8 security, Commit #9
    compatibility, and Commit #10 quality findings) -- it never triggers a
    new verification, regression analysis, security/compatibility/quality
    review, and never mutates anything, so the same underlying state always
    produces the same result.
    """

    gate_id: str
    execution_id: str
    gate_type: str
    status: str
    findings: list
    evaluated_at: datetime
