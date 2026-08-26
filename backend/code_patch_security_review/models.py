from dataclasses import dataclass

AUTH = "AUTH"
INPUT = "INPUT"
SECRETS = "SECRETS"
DATA = "DATA"
DEPENDENCY = "DEPENDENCY"
CATEGORIES = frozenset({AUTH, INPUT, SECRETS, DATA, DEPENDENCY})

INFO = "INFO"
WARNING = "WARNING"
ERROR = "ERROR"
CRITICAL = "CRITICAL"
SEVERITIES = frozenset({INFO, WARNING, ERROR, CRITICAL})


@dataclass(frozen=True)
class LLMCodePatchSecurityFinding:
    """One security finding about an applied Commit #5 patch's current
    generated output, grounded in real evidence -- never a bare claim.

    evidence is always redacted of any matched secret value (see
    LLMCodePatchSecurityService._redact()), for every finding regardless of
    category or source (deterministic or LLM-proposed) -- a finding can
    never itself leak the very credential it flags. severity == CRITICAL is
    the only severity that blocks acceptance (see
    LLMCodePatchSecurityService.blocking()). Analysis is read-only: it
    never mutates the generated output, the execution, or anything
    upstream of it.
    """

    finding_id: str
    execution_id: str
    category: str
    severity: str
    evidence: str
    confidence: float
