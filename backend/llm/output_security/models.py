from dataclasses import dataclass

SECRETS = "SECRETS"
UNSAFE_INSTRUCTION = "UNSAFE_INSTRUCTION"
TOOL_BOUNDARY_BYPASS = "TOOL_BOUNDARY_BYPASS"
CATEGORIES = frozenset({SECRETS, UNSAFE_INSTRUCTION, TOOL_BOUNDARY_BYPASS})

# The only severity these deterministic rules ever emit -- every pattern
# this service matches is an unambiguous leak or bypass attempt, so
# severity and blocking are constant together. Mirrors
# backend.llm.input_security's same choice on the request side.
CRITICAL = "CRITICAL"
SEVERITIES = frozenset({CRITICAL})


@dataclass(frozen=True)
class LLMOutputSecurityFinding:
    """One security finding about an LLMResponse, raised before its content
    may be returned to a user or passed into a downstream project workflow.

    evidence is always redacted of anything matching a secret pattern (see
    LLMOutputSecurityService._redact()) -- a finding can never itself leak
    the credential it flags. blocking is True exactly when severity is
    CRITICAL (see Rules: "Blocking findings prevent downstream
    execution"). Detection is read-only: a finding never mutates the
    response it came from.
    """

    category: str
    severity: str
    evidence: str
    blocking: bool
