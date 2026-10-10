from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class LLMCodePatchCompatibility:
    """The final compiler-compatibility verdict for one applied Commit #5
    execution's current generated output, before it may be accepted.

    Aggregates Commit #7's regression findings (SCHEMA_INCOMPATIBILITY),
    Commit #8's security findings (IMPORT_INCOMPATIBILITY for its
    DEPENDENCY-category findings, SECURITY_INCOMPATIBILITY for the rest),
    this service's own deterministic route/method check against the real
    compiler's own supported structures (backend.compilation_plan.
    ENDPOINT_METHODS), and an LLM pass over the compiler's own generation
    approach -- compatible is True only when none of them produced a
    blocking finding. findings is a list of {"category", "message",
    "blocking"} dicts drawn from all of these sources. Review is
    read-only: it never mutates the generated output, the execution, or
    anything upstream of it.
    """

    review_id: str
    execution_id: str
    compatible: bool
    findings: list
    confidence: float
    reviewed_at: datetime
