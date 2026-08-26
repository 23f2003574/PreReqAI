from dataclasses import dataclass

STYLE = "STYLE"
COMPLEXITY = "COMPLEXITY"
DUPLICATION = "DUPLICATION"
MAINTAINABILITY = "MAINTAINABILITY"
DEAD_CODE = "DEAD_CODE"
CATEGORIES = frozenset({STYLE, COMPLEXITY, DUPLICATION, MAINTAINABILITY, DEAD_CODE})

INFO = "INFO"
WARNING = "WARNING"
ERROR = "ERROR"
CRITICAL = "CRITICAL"
SEVERITIES = frozenset({INFO, WARNING, ERROR, CRITICAL})


@dataclass(frozen=True)
class LLMCodePatchQualityFinding:
    """One maintainability/code-quality finding about an applied Commit #5
    patch's current generated output, grounded in real evidence -- never a
    bare claim.

    evidence always cites either the exact function/construct a
    deterministic `ast` scan found in the current output's own "source"
    (the same source-inspection convention used throughout this codebase,
    e.g. backend.transformation_validation) or a real key path into the
    current output (see LLMCodePatchQualityService._flatten_locations(),
    for an LLM-proposed finding) -- a finding with no real evidence is
    never recorded. severity == CRITICAL is the only severity that blocks
    acceptance (see LLMCodePatchQualityService.blocking()). Analysis is
    read-only: it never mutates the generated output, the execution, or
    anything upstream of it.
    """

    finding_id: str
    execution_id: str
    category: str
    severity: str
    evidence: str
    confidence: float
