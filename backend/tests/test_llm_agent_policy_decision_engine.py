import pytest

from backend.agent_policy_decision import (
    InvalidPolicyDecisionInputError,
    LLMAgentPolicyDecisionEngine,
    PolicyDecision,
)
from backend.agent_policy_engine import ALLOW, DENY, LLMAgentPolicyRule, LLMAgentPolicyService
from backend.agent_policy_resolution import LLMAgentPolicyResolver
from backend.agent_task_planning import READY, LLMAgentPlanStep


def _rule(rule_id, effect, match=None, reason=""):
    return LLMAgentPolicyRule(rule_id=rule_id, effect=effect, match=match or {}, reason=reason)


def _action_from_step(tool_name, **extra) -> dict:
    """A real backend.agent_task_planning.LLMAgentPlanStep, reduced to the
    plain {field: value} action_context shape Commit #1's own
    LLMAgentPolicyEvaluator already evaluates against -- grounding the
    decision engine's tests in the repo's actual plan-step model rather
    than a purely synthetic dict."""
    step = LLMAgentPlanStep(
        step_id="step-1", action=f"call {tool_name}", tool_name=tool_name,
        arguments={}, depends_on=[], status=READY, errors=[],
    )
    return {"tool_name": step.tool_name, **extra}


def _services():
    policy_service = LLMAgentPolicyService()
    resolver = LLMAgentPolicyResolver(policy_service)
    engine = LLMAgentPolicyDecisionEngine()
    return policy_service, resolver, engine


def test_allow():
    policy_service, resolver, engine = _services()
    policy_service.create(
        "notebook-1", "allow-lookup", [_rule("allow-lookup", ALLOW, {"tool_name": "lookup"}, "lookup is safe")]
    )
    resolved = resolver.resolve("notebook-1")

    decision = engine.decide(_action_from_step("lookup"), resolved)

    assert isinstance(decision, PolicyDecision)
    assert decision.decision == ALLOW
    assert len(decision.matched_rules) == 1
    assert decision.matched_rules[0].rule_id == "allow-lookup"
    assert decision.reasons == ["lookup is safe"]
    assert len(decision.provenance) == 1


def test_explicit_deny():
    policy_service, resolver, engine = _services()
    policy_service.create(
        "notebook-1", "deny-delete", [_rule("deny-delete", DENY, {"tool_name": "delete"}, "delete is never permitted")]
    )
    resolved = resolver.resolve("notebook-1")

    decision = engine.decide(_action_from_step("delete"), resolved)

    assert decision.decision == DENY
    assert len(decision.matched_rules) == 1
    assert decision.matched_rules[0].rule_id == "deny-delete"
    assert decision.reasons == ["delete is never permitted"]


def test_conflicting_policies_deny_wins_regardless_of_precedence():
    policy_service, resolver, engine = _services()
    allow_policy = policy_service.create(
        "notebook-1", "allow-all", [_rule("allow-lookup", ALLOW, {"tool_name": "lookup"}, "generally allowed")]
    )
    deny_policy = policy_service.create(
        "notebook-1", "deny-admin", [_rule("deny-lookup-admin", DENY, {"tool_name": "lookup"}, "blocked for this scope")]
    )
    # allow_policy is explicitly given higher precedence than deny_policy --
    # the deny must still win, since precedence only orders evaluation, it
    # never lets a higher-ranked allow override a lower-ranked explicit deny
    resolver.set_precedence(allow_policy.policy_id, higher_than=deny_policy.policy_id)
    resolved = resolver.resolve("notebook-1")
    assert [item.policy.policy_id for item in resolved] == [allow_policy.policy_id, deny_policy.policy_id]

    decision = engine.decide(_action_from_step("lookup"), resolved)

    assert decision.decision == DENY
    assert [rule.rule_id for rule in decision.matched_rules] == ["deny-lookup-admin"]
    assert decision.reasons == ["blocked for this scope"]
    # the allow policy was still evaluated and stays visible in provenance,
    # even though it did not determine the final decision
    assert len(decision.provenance) == 2
    assert {trace.decision.policy_id for trace in decision.provenance} == {
        allow_policy.policy_id,
        deny_policy.policy_id,
    }


def test_multiple_matching_rules_all_recorded():
    policy_service, resolver, engine = _services()
    first = policy_service.create(
        "notebook-1", "first", [_rule("allow-1", ALLOW, {"tool_name": "lookup"}, "reason one")]
    )
    second = policy_service.create(
        "notebook-1", "second", [_rule("allow-2", ALLOW, {"tool_name": "lookup"}, "reason two")]
    )
    resolved = resolver.resolve("notebook-1")

    decision = engine.decide(_action_from_step("lookup"), resolved)

    assert decision.decision == ALLOW
    assert {rule.rule_id for rule in decision.matched_rules} == {"allow-1", "allow-2"}
    assert set(decision.reasons) == {"reason one", "reason two"}
    assert len(decision.provenance) == 2


def test_no_applicable_rules_follows_deny_by_default():
    policy_service, resolver, engine = _services()

    # no resolved policies at all
    empty_decision = engine.decide(_action_from_step("lookup"), [])
    assert empty_decision.decision == DENY
    assert empty_decision.matched_rules == []
    assert empty_decision.provenance == []

    # a resolved policy exists but none of its rules match this action
    policy_service.create(
        "notebook-1", "unrelated", [_rule("allow-other", ALLOW, {"tool_name": "delete"})]
    )
    resolved = resolver.resolve("notebook-1")
    decision = engine.decide(_action_from_step("lookup"), resolved)

    assert decision.decision == DENY
    assert decision.matched_rules == []
    assert len(decision.provenance) == 1


def test_deterministic_decision():
    policy_service, resolver, engine = _services()
    policy_service.create(
        "notebook-1", "allow-lookup", [_rule("allow-lookup", ALLOW, {"tool_name": "lookup"})]
    )
    policy_service.create(
        "notebook-1", "deny-lookup", [_rule("deny-lookup", DENY, {"tool_name": "lookup"})]
    )
    resolved = resolver.resolve("notebook-1")

    first_call = engine.decide(_action_from_step("lookup"), resolved)
    second_call = engine.decide(_action_from_step("lookup"), resolved)

    assert first_call == second_call


def test_provenance_includes_every_resolved_policy():
    policy_service, resolver, engine = _services()
    allowed = policy_service.create(
        "notebook-1", "allow-lookup", [_rule("allow-lookup", ALLOW, {"tool_name": "lookup"})]
    )
    unrelated = policy_service.create(
        "notebook-1", "unrelated", [_rule("allow-delete", ALLOW, {"tool_name": "delete"})]
    )
    resolved = resolver.resolve("notebook-1")

    decision = engine.decide(_action_from_step("lookup"), resolved)

    by_policy_id = {trace.resolved.policy.policy_id: trace for trace in decision.provenance}
    assert set(by_policy_id) == {allowed.policy_id, unrelated.policy_id}

    matched_trace = by_policy_id[allowed.policy_id]
    assert matched_trace.decision.rule_id == "allow-lookup"
    assert matched_trace.resolved.source == "scope:notebook-1"

    unmatched_trace = by_policy_id[unrelated.policy_id]
    assert unmatched_trace.decision.rule_id is None
    assert unmatched_trace.decision.effect == DENY


def test_decide_rejects_invalid_input():
    _, resolver, engine = _services()

    with pytest.raises(InvalidPolicyDecisionInputError):
        engine.decide("not-a-dict", [])

    with pytest.raises(InvalidPolicyDecisionInputError):
        engine.decide({"tool_name": "lookup"}, "not-a-list")

    with pytest.raises(InvalidPolicyDecisionInputError):
        engine.decide({"tool_name": "lookup"}, ["not-a-resolved-policy"])
