from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class LLMAPICompatibilityReview:
    """The final compiler-compatibility verdict for a Commit #4
    recommendation, before it may be approved for compilation.

    Aggregates Commit #5's schema review, Commit #8's risk findings, and
    Commit #10's security findings alongside this service's own
    deterministic method/pattern check and an LLM pass over the compiler's
    own generation approach -- compatible is True only when none of them
    produced a blocking finding. findings is a list of {"category",
    "message", "blocking"} dicts drawn from all of these sources. Review is
    read-only: it never mutates the recommendation, the schemas, the
    notebook, or the compiler.
    """

    review_id: str
    endpoint: str
    compatible: bool
    findings: list
    confidence: float
    reviewed_at: datetime
