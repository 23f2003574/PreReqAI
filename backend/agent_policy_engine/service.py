from .in_memory_store import InMemoryLLMAgentPolicyStore
from .models import ACTIVE, ARCHIVED, STATUSES, LLMAgentPolicy, LLMAgentPolicyRule
from .store import LLMAgentPolicyStore


class UnknownAgentPolicyError(KeyError):
    """Raised when get()/update()/archive() is given a policy_id that was never created."""


class InvalidAgentPolicyError(ValueError):
    """Raised when a policy's scope_id, name, or rules fail validation."""


class InvalidPolicyStatusError(ValueError):
    """Raised when a status argument is not one of STATUSES."""


class DuplicateRuleIdError(InvalidAgentPolicyError):
    """Raised when two rules within the same policy share a rule_id -- a
    rule_id must uniquely identify the rule responsible for a decision
    within its own policy, so provenance never becomes ambiguous."""


class ArchivedPolicyError(ValueError):
    """Raised when update() is given a policy_id that is already ARCHIVED.

    An archived policy is retired, deliberately-preserved history -- the
    same reasoning backend.agent_strategy_library.LLMAgentStrategyService
    already applies to an ARCHIVED strategy. Reviving one requires a
    fresh create() call, not a mutation of the archived record.
    """


class LLMAgentPolicyService:
    """Creates, reads, and retires named, scope-level policies of
    deterministic allow/deny rules governing agent planning/execution
    decisions.

    Not a second governance or security framework: this is bookkeeping
    only. Persistence follows the exact save/get/list_for_scope split
    backend.agent_strategy_library.LLMAgentStrategyService already uses
    (an InMemoryLLMAgentPolicyStore by default, or a JSON-file-backed
    store built on the same backend.storage.AtomicJsonFile), and a rule's
    match constraints reuse
    backend.llm.tool_permissions.LLMToolPermissionPolicy's own {field:
    expected} condition shape rather than a new one.

    This service never evaluates a policy against an action itself --
    that is LLMAgentPolicyEvaluator's job, kept deliberately separate so
    record-keeping and decision-making can be tested and reasoned about
    independently, the same split backend.llm.tool_permissions already
    keeps between registering policies and authorize().
    """

    def __init__(self, store: LLMAgentPolicyStore = None):
        self.store = store if store is not None else InMemoryLLMAgentPolicyStore()

    def create(self, scope_id: str, name: str, rules: list, status: str = ACTIVE) -> LLMAgentPolicy:
        """Record a new policy for scope_id with the given rules.

        Raises:
            InvalidAgentPolicyError: If scope_id, name, or rules is
                missing or the wrong type
            InvalidPolicyRuleError: If any rule's own fields are invalid
            DuplicateRuleIdError: If two rules share a rule_id
            InvalidPolicyStatusError: If status is given and is not one
                of STATUSES
        """
        self._validate_scope_id(scope_id)
        self._validate_name(name)
        self._validate_status(status)
        resolved_rules = self._validate_rules(rules)

        policy = LLMAgentPolicy(scope_id=scope_id, name=name, rules=resolved_rules, status=status)
        return self.store.save(policy)

    def get(self, policy_id: str) -> LLMAgentPolicy:
        policy = self.store.get(policy_id)
        if policy is None:
            raise UnknownAgentPolicyError(policy_id)
        return policy

    def list(self, scope_id: str, status: str = None) -> list:
        self._validate_scope_id(scope_id)
        if status is not None:
            self._validate_status(status)
        return self.store.list_for_scope(scope_id, status)

    def update(self, policy_id: str, name: str = None, rules: list = None) -> LLMAgentPolicy:
        """Update one or both of name/rules on an existing, still-ACTIVE
        policy. Fields left as None are unchanged.

        Raises:
            UnknownAgentPolicyError: If policy_id was never created
            ArchivedPolicyError: If policy_id is already ARCHIVED
            InvalidAgentPolicyError, InvalidPolicyRuleError,
                DuplicateRuleIdError: If name or rules is given and fails
                validation
        """
        policy = self.get(policy_id)
        if policy.status == ARCHIVED:
            raise ArchivedPolicyError(f"policy {policy_id!r} is archived and cannot be updated")

        if name is not None:
            self._validate_name(name)
            policy.name = name
        if rules is not None:
            policy.rules = self._validate_rules(rules)

        return self.store.save(policy)

    def archive(self, policy_id: str) -> LLMAgentPolicy:
        """Retire policy_id by marking it ARCHIVED, never by deleting it --
        an archived policy stays exactly as reachable through get()/
        list() as any other. Idempotent: archiving an already-ARCHIVED
        policy simply returns it unchanged.

        Raises:
            UnknownAgentPolicyError: If policy_id was never created
        """
        policy = self.get(policy_id)
        if policy.status == ARCHIVED:
            return policy

        policy.status = ARCHIVED
        return self.store.save(policy)

    @staticmethod
    def _validate_scope_id(scope_id):
        if not scope_id or not isinstance(scope_id, str):
            raise InvalidAgentPolicyError("scope_id is required and must identify a project/notebook/API")

    @staticmethod
    def _validate_name(name):
        if not name or not isinstance(name, str):
            raise InvalidAgentPolicyError("name is required")

    @staticmethod
    def _validate_status(status):
        if status not in STATUSES:
            raise InvalidPolicyStatusError(f"status {status!r} is not one of {sorted(STATUSES)}")

    @staticmethod
    def _validate_rules(rules) -> list:
        if rules is None or not isinstance(rules, list):
            raise InvalidAgentPolicyError("rules is required and must be a list")

        resolved = []
        seen_ids = set()
        for rule in rules:
            if isinstance(rule, LLMAgentPolicyRule):
                resolved_rule = rule
            elif isinstance(rule, dict):
                resolved_rule = LLMAgentPolicyRule.from_dict(rule)
            else:
                raise InvalidAgentPolicyError(
                    f"each rule must be an LLMAgentPolicyRule or dict, got {type(rule).__name__}"
                )

            if resolved_rule.rule_id in seen_ids:
                raise DuplicateRuleIdError(
                    f"rule_id {resolved_rule.rule_id!r} is duplicated within this policy"
                )
            seen_ids.add(resolved_rule.rule_id)
            resolved.append(resolved_rule)
        return resolved
