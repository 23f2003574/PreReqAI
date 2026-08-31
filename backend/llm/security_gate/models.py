from dataclasses import dataclass
from datetime import datetime
from typing import Optional

PASSED = "PASSED"
FAILED = "FAILED"
STATUSES = frozenset({PASSED, FAILED})


@dataclass(frozen=True)
class LLMSecurityGate:
    """One deterministic pass/fail verdict for whether the current LLM
    security posture is acceptable for downstream execution or release.

    findings is exactly Commit #11's own assess()["findings"] list --
    this gate invents no findings of its own, it only classifies them
    into PASSED/FAILED (see LLMSecurityGateService). Evaluating a gate
    only ever reads Commit #11's already-computed health assessment; it
    never triggers a new one and never mutates anything, so the same
    underlying audit state always produces the same gate.

    Attributes:
        gate_id: This evaluation's unique identifier
        scope: The scope (a request_id, or None for everything) this
            gate was evaluated for -- the same scope Commit #9's own
            metrics already use
        status: PASSED or FAILED
        findings: Commit #11's own findings for the same scope/period
        evaluated_at: When this gate was evaluated
    """

    gate_id: str
    scope: Optional[str]
    status: str
    findings: list
    evaluated_at: datetime
