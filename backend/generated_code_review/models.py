from dataclasses import dataclass

CORRECTNESS = "CORRECTNESS"
SECURITY = "SECURITY"
QUALITY = "QUALITY"
COMPATIBILITY = "COMPATIBILITY"
CATEGORIES = frozenset({CORRECTNESS, SECURITY, QUALITY, COMPATIBILITY})

INFO = "INFO"
WARNING = "WARNING"
ERROR = "ERROR"
CRITICAL = "CRITICAL"
SEVERITIES = frozenset({INFO, WARNING, ERROR, CRITICAL})

APPROVED = "APPROVED"
REJECTED = "REJECTED"
STATUSES = frozenset({APPROVED, REJECTED})


@dataclass(frozen=True)
class LLMGeneratedCodeReview:
    """The review verdict for one backend.compilation_execution CompilerJobResult.

    findings is a list of {"category", "location", "severity", "message"}
    dicts. category is one of CORRECTNESS/SECURITY/QUALITY/COMPATIBILITY.
    location is always either the reviewed job's own job_id or an exact key
    path into that job's own `output` dict (see
    LLMGeneratedCodeReviewService._flatten -- "a.b", "a[0]", ...), so every
    finding is traceable back to real generated output, never a bare claim.
    severity is the highest severity across findings (INFO if there are
    none). status is REJECTED whenever any finding is CRITICAL (see
    LLMGeneratedCodeReviewService.blocking()), APPROVED otherwise.
    Producing this review never mutates the CompilerJobResult, the
    compiler, or anything upstream of it.
    """

    review_id: str
    target: str
    findings: list
    severity: str
    confidence: float
    status: str
