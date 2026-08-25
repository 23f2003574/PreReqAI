from dataclasses import dataclass

INPUT = "INPUT"
AUTH = "AUTH"
SECRETS = "SECRETS"
DATA = "DATA"
CODE = "CODE"
CATEGORIES = frozenset({INPUT, AUTH, SECRETS, DATA, CODE})

INFO = "INFO"
WARNING = "WARNING"
ERROR = "ERROR"
CRITICAL = "CRITICAL"
SEVERITIES = frozenset({INFO, WARNING, ERROR, CRITICAL})


@dataclass(frozen=True)
class LLMAPISecurityFinding:
    """One security finding about a Commit #4 recommendation's endpoint,
    grounded in real evidence -- never a bare claim.

    evidence is a non-empty string citing what this finding is based on --
    a Commit #5 schema review finding, the codebase's own (verified)
    absence of endpoint authentication, a matched secret pattern in the
    function's own source, a real backend.notebook_dependencies DATA/MODEL
    edge, or a dangerous-construct pattern match -- a finding with no real
    evidence is never recorded. severity == CRITICAL is the only severity
    that blocks an exposure recommendation (see
    LLMAPISecurityService.blocking()). Analysis is read-only: it never
    mutates the recommendation, the schemas, the notebook, or the compiler.
    """

    finding_id: str
    endpoint: str
    category: str
    severity: str
    evidence: str
    confidence: float
