from dataclasses import dataclass

APPROVED = "APPROVED"
REJECTED = "REJECTED"
STATUSES = frozenset({APPROVED, REJECTED})


@dataclass(frozen=True)
class LLMAPISchemaReview:
    """The outcome of reviewing one Commit #4 recommendation's already-inferred
    compiler schemas before API generation.

    findings is a list of {"category", "target", "message", "blocking"}
    dicts -- status is APPROVED only when none of them are blocking. This
    service never alters the schemas it reviews (backend.input_schema /
    backend.output_schema), the candidate, or the notebook; it only ever
    reads them.
    """

    review_id: str
    function_name: str
    findings: list
    status: str
    confidence: float
