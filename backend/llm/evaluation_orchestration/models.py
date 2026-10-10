from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from ..evaluation_scoring import MAX_SCORE, MIN_SCORE

REJECTED = "REJECTED"
PASSED = "PASSED"
ACCEPTED = "ACCEPTED"
STATUSES = frozenset({REJECTED, PASSED, ACCEPTED})


class InvalidEvaluationDecisionError(ValueError):
    """Raised when an LLMEvaluationDecision fails validation."""


@dataclass(frozen=True)
class LLMEvaluationDecision:
    """The single, deterministic verdict for one Commit #9 dataset run.

    status is REJECTED when Commit #12's gate rejected it (blocking_findings
    then holds exactly the gate's failed findings); PASSED once the gate
    accepts it, but before this dataset run has actually been made the
    dataset's baseline; ACCEPTED only after an explicit accept() call has
    promoted it, at which point baseline_id names the resulting Commit #11
    baseline. baseline_id is otherwise the dataset's current active
    baseline (or None), read at evaluate() time -- evaluate() itself never
    changes it.
    """

    decision_id: str
    dataset_run_id: str
    provider: str
    model: str
    status: str
    score: Optional[float]
    blocking_findings: list
    baseline_id: Optional[str]
    created_at: datetime

    def validate(self):
        if not self.decision_id or not isinstance(self.decision_id, str):
            raise InvalidEvaluationDecisionError("decision_id is required")

        if not self.dataset_run_id or not isinstance(self.dataset_run_id, str):
            raise InvalidEvaluationDecisionError("dataset_run_id is required")

        if not self.provider or not isinstance(self.provider, str):
            raise InvalidEvaluationDecisionError("provider is required")

        if not self.model or not isinstance(self.model, str):
            raise InvalidEvaluationDecisionError("model is required")

        if self.status not in STATUSES:
            raise InvalidEvaluationDecisionError(f"status must be one of {sorted(STATUSES)}")

        if self.score is not None:
            if isinstance(self.score, bool) or not isinstance(self.score, (int, float)):
                raise InvalidEvaluationDecisionError("score must be a number or None")
            if not (MIN_SCORE <= self.score <= MAX_SCORE):
                raise InvalidEvaluationDecisionError(
                    f"score must be between {MIN_SCORE} and {MAX_SCORE}"
                )

        if not isinstance(self.blocking_findings, list):
            raise InvalidEvaluationDecisionError("blocking_findings must be a list")

        if self.status == REJECTED and not self.blocking_findings:
            raise InvalidEvaluationDecisionError("a REJECTED decision must carry blocking_findings")
        if self.status != REJECTED and self.blocking_findings:
            raise InvalidEvaluationDecisionError(
                "blocking_findings must be empty unless status is REJECTED"
            )

        if self.baseline_id is not None and not isinstance(self.baseline_id, str):
            raise InvalidEvaluationDecisionError("baseline_id must be a string or None")
        if self.status == ACCEPTED and self.baseline_id is None:
            raise InvalidEvaluationDecisionError("an ACCEPTED decision must carry a baseline_id")

        if not isinstance(self.created_at, datetime):
            raise InvalidEvaluationDecisionError("created_at must be a datetime")
