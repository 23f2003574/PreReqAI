from dataclasses import dataclass
from datetime import datetime

ACCEPTED = "ACCEPTED"
REJECTED = "REJECTED"
STATUSES = frozenset({ACCEPTED, REJECTED})


class InvalidEvaluationGateError(ValueError):
    """Raised when an LLMEvaluationGate fails validation."""


@dataclass(frozen=True)
class LLMEvaluationGate:
    """The single accept/reject verdict for one Commit #9 dataset run.

    findings is an ordered list of {"check", "passed", "detail"} entries --
    one per rule this gate enforces -- so a REJECTED verdict is always
    traceable to the specific check(s) that failed, never a bare boolean.
    status is REJECTED if and only if at least one finding failed; nothing
    here computes a new score, it only reads Commit #5/#10/#11's existing
    judgments.
    """

    gate_id: str
    run_id: str
    status: str
    findings: list
    evaluated_at: datetime

    def validate(self):
        if not self.gate_id or not isinstance(self.gate_id, str):
            raise InvalidEvaluationGateError("gate_id is required")

        if not self.run_id or not isinstance(self.run_id, str):
            raise InvalidEvaluationGateError("run_id is required")

        if self.status not in STATUSES:
            raise InvalidEvaluationGateError(f"status must be one of {sorted(STATUSES)}")

        if not isinstance(self.findings, list) or not self.findings:
            raise InvalidEvaluationGateError("findings must be a non-empty list")

        for finding in self.findings:
            if (
                not isinstance(finding, dict)
                or not isinstance(finding.get("check"), str)
                or not finding.get("check")
                or not isinstance(finding.get("passed"), bool)
                or not isinstance(finding.get("detail"), str)
                or not finding.get("detail")
            ):
                raise InvalidEvaluationGateError(
                    "each finding must be a {'check': str, 'passed': bool, 'detail': str} entry"
                )

        all_passed = all(finding["passed"] for finding in self.findings)
        expected_status = ACCEPTED if all_passed else REJECTED
        if self.status != expected_status:
            raise InvalidEvaluationGateError(
                f"status {self.status!r} is inconsistent with findings "
                f"(expected {expected_status!r})"
            )

        if not isinstance(self.evaluated_at, datetime):
            raise InvalidEvaluationGateError("evaluated_at must be a datetime")
