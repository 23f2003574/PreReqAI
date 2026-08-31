from dataclasses import dataclass

PROMPT_INJECTION = "PROMPT_INJECTION"
TOOL_BOUNDARY_BYPASS = "TOOL_BOUNDARY_BYPASS"
CATEGORIES = frozenset({PROMPT_INJECTION, TOOL_BOUNDARY_BYPASS})

# The only severity these deterministic rules ever emit: every pattern this
# service matches is an unambiguous override/bypass attempt, so severity
# and blocking are constant together, unlike backend.api_security_review's
# graded INFO/WARNING/ERROR/CRITICAL scale for LLM-proposed findings.
CRITICAL = "CRITICAL"
SEVERITIES = frozenset({CRITICAL})


@dataclass(frozen=True)
class LLMInputSecurityFinding:
    """One security finding about an LLMRequest, raised before it may reach
    LLMRequestOrchestrationService.execute().

    evidence is always redacted of anything matching a secret pattern (see
    LLMInputSecurityService._redact()) -- a finding can never itself leak
    the credential it flags. blocking is True exactly when severity is
    CRITICAL (see Rules: "CRITICAL/blocking findings prevent the LLM
    request"). Detection is read-only: a finding never mutates the
    request or any message it came from.
    """

    category: str
    severity: str
    evidence: str
    blocking: bool
