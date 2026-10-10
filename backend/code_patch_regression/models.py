from dataclasses import dataclass
from datetime import datetime

CRITICAL = "CRITICAL"
MINOR = "MINOR"
SEVERITIES = frozenset({CRITICAL, MINOR})


@dataclass(frozen=True)
class LLMCodePatchRegression:
    """One detected behavioral difference, for a single Commit #1 review
    category, between a Commit #5 execution's pre-patch baseline review and
    its current (post-patch) review.

    expected/actual are each {"blocking", "count"} dicts -- expected
    summarizes the pre-patch baseline review (backend.generated_code_review,
    already on record as suggestion.review_id) findings for this category;
    actual summarizes a freshly re-run review's findings for the same
    category -- the same "reuse the existing review pipeline as the test"
    approach Commit #6 already uses, never a second, parallel behavioral
    framework. severity is CRITICAL when a category became blocking that
    wasn't blocking in the baseline (a regression Commit #6 alone wouldn't
    necessarily catch, since Commit #6 only asks whether the *original*
    finding got resolved), MINOR when new, non-blocking findings appeared.
    Detecting this never mutates the generated output, the execution, or
    anything upstream of it.
    """

    regression_id: str
    execution_id: str
    test_id: str
    expected: dict
    actual: dict
    severity: str
    detected_at: datetime
