from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


@dataclass(frozen=True)
class LLMAgentPolicyDecisionAudit:
    """One immutable, append-only snapshot of one Commit #1-#5 policy
    decision, made observable after the fact.

    Deliberately a compact, reference-based record rather than a copy of
    everything Commit #1-#5 already durably store: matched_rules and
    exceptions each carry only the identifiers (policy_id/rule_id/
    exception_id) and short reason text needed to trace a decision back
    to the real LLMAgentPolicy/LLMAgentPolicyException records Commit #1/
    #5 already keep -- never a second copy of a policy's full rule set or
    an exception's full match constraint. The action itself is
    represented only by execution_or_action_id, never by the action's own
    arguments/payload -- the same "what is deliberately absent" discipline
    backend.llm.tool_audit.LLMToolAudit already applies to a tool call's
    arguments and output, since either can carry credentials and neither
    is needed to reconstruct which policies decided what.

    Never updated or deleted once recorded -- LLMAgentPolicyAuditService.record()
    only ever appends a new LLMAgentPolicyDecisionAudit, the same
    append-only discipline
    backend.agent_strategy_decision_audit.LLMAgentStrategyDecision already
    establishes for this repository's other decision trail.

    Attributes:
        scope_id: The scope this decision was made within. An audit
            record is never consulted for, or leaks into, any other scope
        execution_or_action_id: The real identifier of the action this
            decision governed -- an execution_id once one exists, the
            same "whatever identifier was actually available" reasoning
            backend.agent_strategy_decision_audit.LLMAgentStrategyDecision
            already documents for its own execution_or_task_id
        decision: The final ALLOW/DENY verdict (Commit #1's own
            vocabulary, reused as-is)
        matched_rules: The policy_id/rule_id/effect/reason of every
            LLMAgentPolicyDecision that determined this verdict
        exceptions: The exception_id/policy_id/reason of every Commit #5
            LLMAgentPolicyException that was applied
        reasons: The decision's own reason strings, redacted
    """

    scope_id: str
    execution_or_action_id: str
    decision: str
    matched_rules: list
    exceptions: list
    reasons: list
    audit_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "LLMAgentPolicyDecisionAudit":
        payload = dict(data)
        value = payload.get("created_at")
        if isinstance(value, str):
            payload["created_at"] = datetime.fromisoformat(value)
        return cls(**payload)
