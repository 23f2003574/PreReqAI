import re

from backend.agent_policy_decision import PolicyDecision

from .in_memory_store import InMemoryLLMAgentPolicyDecisionAuditStore
from .models import LLMAgentPolicyDecisionAudit
from .store import LLMAgentPolicyDecisionAuditStore

# Same secret-detection/redaction convention already kept locally by
# backend.llm.tool_audit, backend.agent_strategy_decision_audit,
# backend.agent_execution_memory, and backend.agent_strategy_library --
# kept local here too rather than refactoring any of those.
_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{10,}"),
    re.compile(r"AKIA[A-Z0-9]{12,}"),
    re.compile(r"(?i)bearer\s+\S+"),
    re.compile(r"(?i)\b(api[_-]?key|token|secret|password)\s*[:=]\s*\S+"),
    re.compile(r"^[A-Fa-f0-9]{32,}$"),
    re.compile(r"^[A-Za-z0-9+/]{40,}={0,2}$"),
)


def _looks_secret(value: str) -> bool:
    return any(pattern.search(value) for pattern in _SECRET_PATTERNS)


def _redact(value: str) -> str:
    return "[REDACTED]" if _looks_secret(value) else value


class UnknownPolicyDecisionAuditError(KeyError):
    """Raised when get() is given an audit_id that was never recorded."""


class LLMAgentPolicyAuditService:
    """Makes Commit #1-#5's policy decisions observable after the fact,
    as one append-only, scope-isolated decision trail.

    Not a new audit framework: persistence follows the exact save/get/
    list_for_-- split
    backend.agent_strategy_decision_audit.LLMAgentStrategyDecisionAuditService
    already established for this repository's other decision trail (an
    InMemoryLLMAgentPolicyDecisionAuditStore by default, or the
    JSON-file-backed store built on the same
    backend.storage.AtomicJsonFile), and string fields are passed through
    the same secret-redaction convention
    backend.llm.tool_audit.LLMToolAuditService already applies to its own
    subject/reason fields, rather than a second detection scheme.

    record() takes the real, already-computed Commit #3-#5 PolicyDecision
    verbatim -- it never re-evaluates a policy and never calls
    LLMAgentPolicyEvaluator/LLMAgentPolicyResolver/
    LLMAgentPolicyDecisionEngine/LLMAgentPolicyEnforcement itself, and it
    never mutates the decision, a policy, or an exception it reads.
    Recording is always the last thing that happens to a decision already
    fully made, so auditing can never change what was decided, by
    construction -- and never stores the action's own arguments/payload,
    the same "what is deliberately absent" discipline
    backend.llm.tool_audit.LLMToolAudit already applies (see
    LLMAgentPolicyDecisionAudit).
    """

    def __init__(self, store: LLMAgentPolicyDecisionAuditStore = None):
        self.store = store if store is not None else InMemoryLLMAgentPolicyDecisionAuditStore()

    def record(
        self, scope_id: str, execution_or_action_id: str, decision: PolicyDecision
    ) -> LLMAgentPolicyDecisionAudit:
        """Append one audit record for an already-computed PolicyDecision.

        Raises:
            ValueError: If scope_id or execution_or_action_id is missing,
                or decision is not a PolicyDecision
        """
        self._validate_text(scope_id, "scope_id")
        self._validate_text(execution_or_action_id, "execution_or_action_id")
        if not isinstance(decision, PolicyDecision):
            raise ValueError(f"decision must be a PolicyDecision, got {type(decision).__name__}")

        matched_rules = [
            {
                "policy_id": entry.policy_id,
                "rule_id": entry.rule_id,
                "effect": entry.effect,
                "reason": _redact(entry.reason) if entry.reason else entry.reason,
            }
            for entry in decision.matched_rules
        ]
        exceptions = [
            {
                "exception_id": exception.exception_id,
                "policy_id": exception.policy_id,
                "reason": _redact(exception.reason),
            }
            for exception in decision.exceptions_applied
        ]
        reasons = [_redact(reason) for reason in decision.reasons]

        record = LLMAgentPolicyDecisionAudit(
            scope_id=scope_id,
            execution_or_action_id=execution_or_action_id,
            decision=decision.decision,
            matched_rules=matched_rules,
            exceptions=exceptions,
            reasons=reasons,
        )
        return self.store.save(record)

    def get(self, audit_id: str) -> LLMAgentPolicyDecisionAudit:
        record = self.store.get(audit_id)
        if record is None:
            raise UnknownPolicyDecisionAuditError(audit_id)
        return record

    def list_for_execution(self, execution_or_action_id: str) -> list:
        """Every audit record for execution_or_action_id, oldest first."""
        self._validate_text(execution_or_action_id, "execution_or_action_id")
        return self.store.list_for_execution(execution_or_action_id)

    def list_for_scope(self, scope_id: str) -> list:
        """Every audit record for scope_id, oldest first -- never
        includes a record from any other scope."""
        self._validate_text(scope_id, "scope_id")
        return self.store.list_for_scope(scope_id)

    @staticmethod
    def _validate_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise ValueError(f"{field_name} is required")
