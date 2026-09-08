from backend.agent_capability_registry import ACTIVE as CAPABILITY_ACTIVE
from backend.agent_capability_registry import ARCHIVED as CAPABILITY_ARCHIVED
from backend.agent_capability_registry import LLMAgentCapabilityRegistry
from backend.agent_policy_engine import DENY, LLMAgentPolicyEvaluator
from backend.agent_policy_resolution import LLMAgentPolicyResolver

from .models import ResolvedAgentCapabilities


class InvalidCapabilityResolutionError(ValueError):
    """Raised when resolve() is given a missing/blank agent_id or
    scope_id, or a context that is not a dict."""


class LLMAgentCapabilityResolver:
    """Deterministically resolves which Commit #1 registered capabilities
    are available to one agent in one scope/context.

    Not a second capability or permission system: capability lookup is
    entirely Commit #1's own LLMAgentCapabilityRegistry.list() (so
    ARCHIVED capabilities are excluded from the base set exactly the way
    every other consumer in this repository already treats an archived
    record), and scope-level restrictions are entirely
    backend.agent_policy_resolution.LLMAgentPolicyResolver +
    backend.agent_policy_engine.LLMAgentPolicyEvaluator -- the exact
    ACTIVE-policy resolution and {field: expected} rule matching every
    other policy consumer in this repository already reuses, never a
    duplicate authorization engine. policy_service is an optional
    collaborator (the same duck-typed "used only if given" shape
    backend.llm.tool_permissions.LLMToolPermissionService.__init__'s own
    invocation_service already uses): when omitted, no scope has any
    policy restriction at all, so every ACTIVE capability resolves
    available; when given, resolve() builds its own
    LLMAgentPolicyResolver(policy_service) internally.

    Each ACTIVE capability is checked against scope_id's own
    ACTIVE policies (already scope-isolated and ARCHIVED-excluded by
    LLMAgentPolicyResolver.resolve()) via one
    LLMAgentPolicyEvaluator.evaluate() call per resolved policy, matching
    against an action dict of {**context, "agent_id", "scope_id",
    "capability_id", "category"} -- agent_id is always present in this
    action dict, so an agent-specific restriction is expressed as an
    ordinary policy rule matching on it (e.g. match={"agent_id": "..."})
    rather than a second, agent-specific permission mechanism; "when
    supported" (see Rules) means exactly this -- a caller who wires up
    such a rule gets agent-specific exclusion, one who never does simply
    never sees it.

    This resolver's default posture is deliberately the opposite of
    LLMAgentPolicyEvaluator's/LLMAgentPolicyDecisionEngine's own
    "deny unless something explicitly allows it": resolve() is a
    discovery/inventory function ("what capabilities exist for this
    agent/scope"), not an execution gate ("may this specific call
    proceed") -- that stricter gate is exactly what
    backend.agent_policy_decision.LLMAgentPolicyDecisionEngine and
    backend.llm.tool_permissions.LLMToolPermissionService already are,
    and a caller still must run one of those before actually invoking a
    capability (resolve() never executes anything). Here, a capability
    stays included unless a policy rule *explicitly* denies it (a rule
    that actually matched, with effect DENY); the complete absence of any
    matching rule -- including a scope with no policies configured at
    all -- excludes nothing. An explicit deny always wins regardless of
    any competing allow, the same "explicit deny always wins" convention
    every policy consumer in this repository already applies; an
    explicit allow changes nothing here since inclusion is already the
    default.

    resolve() never mutates the capability registry, the policy engine,
    or anything it is given -- it only ever reads. The same
    (agent_id, scope_id, context, and current registry/policy state)
    always resolves to the same ResolvedAgentCapabilities.
    """

    def __init__(self, capability_registry: LLMAgentCapabilityRegistry, policy_service=None):
        self._capability_registry = capability_registry
        self._policy_resolver = LLMAgentPolicyResolver(policy_service) if policy_service is not None else None
        self._evaluator = LLMAgentPolicyEvaluator()

    def resolve(self, agent_id: str, scope_id: str, context: dict = None) -> ResolvedAgentCapabilities:
        """Resolve every capability available to agent_id in scope_id.

        context is an optional dict of additional fields merged into the
        action every policy rule is matched against (e.g. a role or
        request attribute a scope's own policy rules choose to key on).
        It never overrides agent_id, scope_id, capability_id, or
        category -- those four are always the resolver's own values.

        Raises:
            InvalidCapabilityResolutionError: If agent_id or scope_id is
                missing/blank, or context is given and is not a dict
        """
        self._validate_identifier(agent_id, "agent_id")
        self._validate_identifier(scope_id, "scope_id")
        if context is None:
            context = {}
        elif not isinstance(context, dict):
            raise InvalidCapabilityResolutionError(
                f"context must be a dict when given, got {type(context).__name__}"
            )

        resolved_policies = self._policy_resolver.resolve(scope_id) if self._policy_resolver is not None else []

        included = []
        excluded = []
        reasons = {}

        archived = sorted(
            self._capability_registry.list(status=CAPABILITY_ARCHIVED), key=lambda c: c.capability_id
        )
        for capability in archived:
            reasons[capability.capability_id] = (
                f"capability {capability.capability_id!r} is archived and excluded from resolution"
            )
            excluded.append(capability)

        active = sorted(
            self._capability_registry.list(status=CAPABILITY_ACTIVE), key=lambda c: c.capability_id
        )
        for capability in active:
            action = dict(context)
            action.update(
                {
                    "agent_id": agent_id,
                    "scope_id": scope_id,
                    "capability_id": capability.capability_id,
                    "category": capability.category,
                }
            )

            denial = self._first_explicit_denial(resolved_policies, action)
            if denial is not None:
                reasons[capability.capability_id] = (
                    f"capability {capability.capability_id!r} denied for agent {agent_id!r} in "
                    f"scope {scope_id!r} by policy {denial.policy_id!r} rule {denial.rule_id!r}: {denial.reason}"
                )
                excluded.append(capability)
                continue

            reasons[capability.capability_id] = (
                f"capability {capability.capability_id!r} is active and not restricted by any "
                f"policy for agent {agent_id!r} in scope {scope_id!r}"
            )
            included.append(capability)

        return ResolvedAgentCapabilities(
            agent_id=agent_id,
            scope_id=scope_id,
            capabilities=included,
            excluded_capabilities=excluded,
            resolution_reasons=reasons,
        )

    def _first_explicit_denial(self, resolved_policies: list, action: dict):
        """The first ResolvedPolicy (in precedence order) whose own
        rules explicitly deny action -- a rule that actually matched,
        with effect DENY, never a policy's own rule-less default-deny
        (that carries rule_id=None, and never restricts a capability
        resolution on its own)."""
        for resolved in resolved_policies:
            decision = self._evaluator.evaluate(resolved.policy, action)
            if decision.rule_id is not None and decision.effect == DENY:
                return decision
        return None

    @staticmethod
    def _validate_identifier(value, field_name):
        if not value or not isinstance(value, str):
            raise InvalidCapabilityResolutionError(f"{field_name} is required and must be a non-empty string")
