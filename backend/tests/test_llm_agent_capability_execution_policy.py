import pytest

from backend.agent_capability_execution_policy import (
    CapabilityExecutionPolicyResult,
    InvalidCapabilityExecutionPolicyError,
    LLMAgentCapabilityExecutionPolicy,
)
from backend.agent_capability_registry import LLMAgentCapability, LLMAgentCapabilityRegistry
from backend.agent_policy_engine import ALLOW, DENY, LLMAgentPolicyService
from backend.agent_policy_risk_assessment import LEVEL_CRITICAL, LEVEL_LOW
from backend.agent_risk_profile import LLMAgentRiskProfileService
from backend.agent_risk_profile_resolution import LLMAgentRiskProfileResolver


def _allow_rule(capability_id="web-search", rule_id="allow-it"):
    return {"rule_id": rule_id, "effect": ALLOW, "match": {"capability_id": capability_id}}


def _deny_rule(capability_id="web-search", rule_id="deny-it"):
    return {"rule_id": rule_id, "effect": DENY, "match": {"capability_id": capability_id}}


def test_allowed_capability_passes():
    policy_service = LLMAgentPolicyService()
    policy_service.create("scope-1", "allow-web-search", [_allow_rule()])
    evaluator = LLMAgentCapabilityExecutionPolicy(policy_service)

    result = evaluator.evaluate("agent-1", "web-search", "scope-1")

    assert isinstance(result, CapabilityExecutionPolicyResult)
    assert result.allowed is True
    assert result.decision == ALLOW
    assert result.denials == []
    assert len(result.matched_policies) == 1


def test_explicit_policy_denial_blocks_execution():
    policy_service = LLMAgentPolicyService()
    policy_service.create("scope-1", "deny-web-search", [_deny_rule()])
    evaluator = LLMAgentCapabilityExecutionPolicy(policy_service)

    result = evaluator.evaluate("agent-1", "web-search", "scope-1")

    assert result.allowed is False
    assert result.decision == DENY
    assert len(result.denials) == 1


def test_no_policy_at_all_denies_by_default():
    policy_service = LLMAgentPolicyService()
    evaluator = LLMAgentCapabilityExecutionPolicy(policy_service)

    result = evaluator.evaluate("agent-1", "web-search", "scope-1")

    assert result.allowed is False
    assert result.decision == DENY
    assert result.matched_policies == []
    assert len(result.reasons) >= 1


def test_scope_specific_policy_is_respected():
    policy_service = LLMAgentPolicyService()
    policy_service.create("scope-1", "allow-web-search", [_allow_rule()])
    evaluator = LLMAgentCapabilityExecutionPolicy(policy_service)

    allowed_scope = evaluator.evaluate("agent-1", "web-search", "scope-1")
    assert allowed_scope.allowed is True

    other_scope = evaluator.evaluate("agent-1", "web-search", "scope-2")
    assert other_scope.allowed is False


def test_conflicting_policy_behavior_follows_existing_engine_semantics():
    policy_service = LLMAgentPolicyService()
    policy_service.create("scope-1", "allow-web-search", [_allow_rule(rule_id="allow-it")])
    policy_service.create("scope-1", "deny-web-search", [_deny_rule(rule_id="deny-it")])
    evaluator = LLMAgentCapabilityExecutionPolicy(policy_service)

    result = evaluator.evaluate("agent-1", "web-search", "scope-1")

    # explicit deny always wins, regardless of a competing allow -- the
    # same semantics LLMAgentPolicyDecisionEngine already guarantees
    assert result.allowed is False
    assert result.decision == DENY


def test_risk_restrictions_respected_when_already_represented():
    policy_service = LLMAgentPolicyService()
    policy_service.create("scope-1", "allow-web-search", [_allow_rule()])

    risk_profile_service = LLMAgentRiskProfileService()
    risk_profile_service.create("scope-1", "critical-default", default_level=LEVEL_CRITICAL)
    risk_resolver = LLMAgentRiskProfileResolver(risk_profile_service)

    evaluator = LLMAgentCapabilityExecutionPolicy(policy_service, risk_profile_resolver=risk_resolver)

    result = evaluator.evaluate("agent-1", "web-search", "scope-1")

    # base policy alone would allow, but the risk layer's CRITICAL level
    # denies -- an explicit denial is never silently overridden
    assert result.allowed is False
    assert result.decision == DENY
    assert any("risk profile" in reason for reason in result.reasons)
    assert any("risk profile" in denial for denial in result.denials)


def test_risk_layer_never_reopens_a_base_denial():
    policy_service = LLMAgentPolicyService()
    policy_service.create("scope-1", "deny-web-search", [_deny_rule()])

    risk_profile_service = LLMAgentRiskProfileService()
    risk_profile_service.create("scope-1", "low-default", default_level=LEVEL_LOW)
    risk_resolver = LLMAgentRiskProfileResolver(risk_profile_service)

    evaluator = LLMAgentCapabilityExecutionPolicy(policy_service, risk_profile_resolver=risk_resolver)

    result = evaluator.evaluate("agent-1", "web-search", "scope-1")

    assert result.allowed is False
    assert result.decision == DENY


def test_risk_layer_skipped_when_not_configured():
    policy_service = LLMAgentPolicyService()
    policy_service.create("scope-1", "allow-web-search", [_allow_rule()])
    evaluator = LLMAgentCapabilityExecutionPolicy(policy_service)

    result = evaluator.evaluate("agent-1", "web-search", "scope-1")

    assert result.allowed is True
    assert result.warnings == []


def test_decision_provenance_is_returned():
    policy_service = LLMAgentPolicyService()
    policy_service.create("scope-1", "allow-web-search", [_allow_rule()])
    evaluator = LLMAgentCapabilityExecutionPolicy(policy_service)

    result = evaluator.evaluate("agent-1", "web-search", "scope-1")

    assert result.matched_policies[0].policy_id is not None
    assert result.matched_policies[0].rule_id == "allow-it"
    assert len(result.reasons) >= 1


def test_evaluation_performs_no_state_mutation():
    policy_service = LLMAgentPolicyService()
    created = policy_service.create("scope-1", "allow-web-search", [_allow_rule()])

    registry = LLMAgentCapabilityRegistry()
    registry.register(
        LLMAgentCapability(capability_id="web-search", name="Web Search", description="d", category="retrieval")
    )
    evaluator = LLMAgentCapabilityExecutionPolicy(policy_service, capability_registry=registry)

    before_policy = policy_service.get(created.policy_id)
    before_capability = registry.get("web-search")

    evaluator.evaluate("agent-1", "web-search", "scope-1")

    assert policy_service.get(created.policy_id) == before_policy
    assert registry.get("web-search") == before_capability


def test_evaluation_is_deterministic():
    policy_service = LLMAgentPolicyService()
    policy_service.create("scope-1", "allow-web-search", [_allow_rule()])
    evaluator = LLMAgentCapabilityExecutionPolicy(policy_service)

    first = evaluator.evaluate("agent-1", "web-search", "scope-1", context={"role": "admin"})
    second = evaluator.evaluate("agent-1", "web-search", "scope-1", context={"role": "admin"})

    assert first == second


def test_validation_errors():
    policy_service = LLMAgentPolicyService()
    evaluator = LLMAgentCapabilityExecutionPolicy(policy_service)

    with pytest.raises(InvalidCapabilityExecutionPolicyError):
        evaluator.evaluate("", "web-search", "scope-1")
    with pytest.raises(InvalidCapabilityExecutionPolicyError):
        evaluator.evaluate("agent-1", "", "scope-1")
    with pytest.raises(InvalidCapabilityExecutionPolicyError):
        evaluator.evaluate("agent-1", "web-search", "")
    with pytest.raises(InvalidCapabilityExecutionPolicyError):
        evaluator.evaluate("agent-1", "web-search", "scope-1", context="not-a-dict")
