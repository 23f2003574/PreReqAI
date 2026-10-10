from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

INPUT = "INPUT"
OUTPUT = "OUTPUT"
DIRECTIONS = frozenset({INPUT, OUTPUT})


@dataclass(frozen=True)
class LLMSecurityAudit:
    """One immutable snapshot of a Commit #5 policy decision for one
    direction (input or output) of one LLM request.

    Follows this codebase's existing append-only audit convention
    (LLMRequestAudit, LLMToolAudit, LLMTransformationAudit): a snapshot is
    never mutated once recorded -- LLMSecurityAuditService only ever
    appends a new one.

    What is deliberately absent: the request's messages, the response's
    content, and anything that looks like a secret or credential. decision
    is Commit #5's own ALLOW/REDACT/BLOCK action; policy_ids names the
    Commit #4 sensitive-data policies that actually applied (see
    LLMSensitiveDataPolicyService.applicable_policy_ids()); finding_types
    names the Commit #1/#2 finding categories that were raised (e.g.
    "PROMPT_INJECTION", "SECRETS") -- never a finding's own evidence text,
    which is exactly where a redacted secret's surrounding context would
    otherwise end up stored. A tool-call proposal is audited the same way
    as any other response: it reaches this trail as an ordinary OUTPUT
    snapshot, the same shape as every other one, because Commit #5 never
    special-cases it either.

    Attributes:
        audit_id: This snapshot's unique identifier
        request_id: The LLM request/conversation this decision was made
            for -- the same identifier already used throughout
            backend.llm (LLMRequestOrchestrationService.execute(),
            LLMRequestAuditService.start(), LLMToolAuditService.start())
        direction: INPUT or OUTPUT
        decision: The Commit #5 action: ALLOW, REDACT, or BLOCK
        policy_ids: The Commit #4 policies that applied, in no particular
            order
        finding_types: The Commit #1/#2 finding categories raised, in no
            particular order
        created_at: When this snapshot was recorded
    """

    audit_id: str
    request_id: str
    direction: str
    decision: str
    policy_ids: tuple = field(default_factory=tuple)
    finding_types: tuple = field(default_factory=tuple)
    created_at: Optional[datetime] = None
