from dataclasses import dataclass

INPUT = "INPUT"
OUTPUT = "OUTPUT"
DEPENDENCY = "DEPENDENCY"
SECURITY = "SECURITY"
RELIABILITY = "RELIABILITY"
CATEGORIES = frozenset({INPUT, OUTPUT, DEPENDENCY, SECURITY, RELIABILITY})

INFO = "INFO"
WARNING = "WARNING"
ERROR = "ERROR"
CRITICAL = "CRITICAL"
SEVERITIES = frozenset({INFO, WARNING, ERROR, CRITICAL})


@dataclass(frozen=True)
class LLMAPIRiskFinding:
    """One risk finding about a Commit #4 recommendation's endpoint, grounded
    in real evidence -- never a bare claim.

    evidence is a non-empty string citing what this finding is based on --
    a Commit #5 schema review finding, a real backend.notebook_dependencies
    edge, a source pattern match, or a Commit #7 test-coverage gap -- a
    finding with no real evidence is never recorded. severity == CRITICAL
    is the only severity that blocks a compilation recommendation (see
    LLMAPIRiskService.blocking()). Analysis is read-only: it never mutates
    the recommendation, the schemas, the notebook, or the compiler.
    """

    finding_id: str
    endpoint: str
    category: str
    severity: str
    evidence: str
    confidence: float
