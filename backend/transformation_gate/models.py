from dataclasses import dataclass
from datetime import datetime

VERIFICATION = "VERIFICATION"
REGRESSION = "REGRESSION"
SECURITY = "SECURITY"
QUALITY = "QUALITY"
GATE_TYPES = frozenset({VERIFICATION, REGRESSION, SECURITY, QUALITY})

PASSED = "PASSED"
FAILED = "FAILED"
STATUSES = frozenset({PASSED, FAILED})


@dataclass(frozen=True)
class LLMTransformationGate:
    """One release gate's deterministic evaluation for an applied execution.

    findings is a list of {"category", "message", "blocking"} dicts --
    status is FAILED whenever any of them is blocking, PASSED otherwise.
    Evaluating a gate only ever reads already-computed state (Commit #6
    verification, Commit #7 regression analysis, the notebook's own
    code_quality findings, and a static pattern-scan of already-applied
    source) -- it never triggers a new analysis and never mutates
    anything, so the same underlying state always produces the same
    result.
    """

    gate_id: str
    execution_id: str
    gate_type: str
    status: str
    findings: list
    evaluated_at: datetime
