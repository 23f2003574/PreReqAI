from .models import ALLOW, ARCHIVED, DENY, LLMAgentPolicy, LLMAgentPolicyDecision


class InvalidPolicyEvaluationError(ValueError):
    """Raised when evaluate() is given a policy that is not an
    LLMAgentPolicy, or an action/context that is not a dict."""


class LLMAgentPolicyEvaluator:
    """Deterministically evaluates one action/context against one
    LLMAgentPolicy's rules, without ever making an LLM call.

    Follows the exact authorization model
    backend.llm.tool_permissions.LLMToolPermissionService.authorize()
    already established for tool calls, applied here to one policy's own
    rules list instead of a service's registered per-tool policies:
    within one evaluation, every rule whose match constraints hold
    against `action` is collected in the policy's own rules order, an
    explicit DENY among them always wins over any competing ALLOW
    (however that ALLOW rule happens to be ordered), and no matching rule
    at all denies by default -- the same "deny unless something
    explicitly allows it" default authorize() already uses. Match
    constraints reuse
    backend.llm.tool_permissions.LLMToolPermissionPolicy.conditions's own
    {field: expected} shape as-is (expected may be a single value or a
    list/tuple of acceptable values; a field `action` does not carry can
    never satisfy a constraint), rather than a second matching scheme.

    An ARCHIVED policy is treated the way authorize() already treats a
    disabled tool: retired, so it denies unconditionally regardless of
    what its rules say -- evaluate() never resurrects an archived
    policy's rules.

    evaluate() never mutates the policy and never calls
    LLMAgentPolicyService itself -- it is pure decision-making over
    whatever LLMAgentPolicy it is given, so the same (policy, action)
    pair always reaches the same LLMAgentPolicyDecision regardless of how
    many times, or in what order, evaluate() is called.
    """

    @staticmethod
    def _constraints_met(match: dict, action: dict) -> bool:
        for field_name, expected in match.items():
            if field_name not in action:
                return False
            actual = action[field_name]
            if isinstance(expected, (list, tuple, set, frozenset)):
                if actual not in expected:
                    return False
            elif actual != expected:
                return False
        return True

    def evaluate(self, policy: LLMAgentPolicy, action: dict) -> LLMAgentPolicyDecision:
        """Decide whether `action` is allowed under `policy`.

        action is an arbitrary {field: value} dict describing the agent
        action/context being checked (e.g. tool_name, step kind, or any
        other field a policy's rules choose to match on).

        Raises:
            InvalidPolicyEvaluationError: If policy is not an
                LLMAgentPolicy, or action is not a dict
        """
        if not isinstance(policy, LLMAgentPolicy):
            raise InvalidPolicyEvaluationError(
                f"policy must be an LLMAgentPolicy, got {type(policy).__name__}"
            )
        if not isinstance(action, dict):
            raise InvalidPolicyEvaluationError(f"action must be a dict, got {type(action).__name__}")

        if policy.status == ARCHIVED:
            return LLMAgentPolicyDecision(
                allowed=False,
                effect=DENY,
                policy_id=policy.policy_id,
                rule_id=None,
                reason=f"policy {policy.policy_id!r} is archived and no longer in effect",
            )

        matching = [rule for rule in policy.rules if self._constraints_met(rule.match, action)]

        # Rule: an explicit deny overrides any allow, regardless of how
        # specific or how the competing allow rule is ordered.
        denials = [rule for rule in matching if rule.effect == DENY]
        if denials:
            rule = denials[0]
            return LLMAgentPolicyDecision(
                allowed=False,
                effect=DENY,
                policy_id=policy.policy_id,
                rule_id=rule.rule_id,
                reason=rule.reason or f"rule {rule.rule_id!r} explicitly denies this action",
            )

        allowances = [rule for rule in matching if rule.effect == ALLOW]
        if allowances:
            rule = allowances[0]
            return LLMAgentPolicyDecision(
                allowed=True,
                effect=ALLOW,
                policy_id=policy.policy_id,
                rule_id=rule.rule_id,
                reason=rule.reason or f"rule {rule.rule_id!r} allows this action",
            )

        return LLMAgentPolicyDecision(
            allowed=False,
            effect=DENY,
            policy_id=policy.policy_id,
            rule_id=None,
            reason=f"no rule in policy {policy.policy_id!r} matches this action; denied by default",
        )
