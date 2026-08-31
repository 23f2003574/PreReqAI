from dataclasses import dataclass, field

from ..sensitive_data_policy import ACTIONS, ALLOW, BLOCK, REDACT

__all__ = ["ACTIONS", "ALLOW", "BLOCK", "REDACT", "LLMPolicyDecision"]


@dataclass(frozen=True)
class LLMPolicyDecision:
    """The combined outcome of security validation and sensitive-data
    policy for one LLMRequest or LLMResponse, at the point it crosses the
    LLM pipeline boundary.

    action is Commit #4's own ALLOW/REDACT/BLOCK vocabulary, reused
    directly rather than a second one -- it is what enforce_input()/
    enforce_output() actually act on. security_findings holds every
    Commit #1/#2 finding for the checked request/response (empty if
    none). blocking is True whenever any security finding was itself
    blocking, or the sensitive-data action was BLOCK -- either one alone
    is enough (see Rules: "Blocking policy always wins"), and action is
    then always BLOCK too. reason is a short, human-readable summary of
    why this decision was reached.
    """

    action: str
    blocking: bool
    security_findings: list = field(default_factory=list)
    reason: str = ""
