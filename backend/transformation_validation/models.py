from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class LLMTransformationValidation:
    """The outcome of validating one LLMCodeTransformationPlan before it may be applied.

    findings is a list of {"category", "target", "message", "blocking"}
    dicts -- valid is True only when none of them are blocking. Producing
    this record never mutates the plan, the notebook analysis, or anything
    upstream of it; it only ever reads them.
    """

    validation_id: str
    plan_id: str
    valid: bool
    findings: list
    checked_at: datetime
