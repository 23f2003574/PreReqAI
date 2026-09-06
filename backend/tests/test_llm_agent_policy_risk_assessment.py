import pytest

from backend.agent_policy_audit import LLMAgentPolicyAuditService
from backend.agent_policy_decision import LLMAgentPolicyDecisionEngine
from backend.agent_policy_engine import ALLOW, DENY, LLMAgentPolicyRule, LLMAgentPolicyService
from backend.agent_policy_enforcement import LLMAgentPolicyEnforcement
from backend.agent_policy_resolution import LLMAgentPolicyResolver
from backend.agent_policy_risk_assessment import (
    LEVEL_CRITICAL,
    LEVEL_HIGH,
    LEVEL_LOW,
    InvalidActionContextError,
    LLMAgentPolicyRiskAssessor,
    RiskAssessment,
)
from backend.llm.tools import LLMToolRegistryService

SCHEMA = {"type": "object", "properties": {"topic": {"type": "string"}}, "required": []}


def _rule(rule_id, effect, match=None, reason=""):
    return LLMAgentPolicyRule(rule_id=rule_id, effect=effect, match=match or {}, reason=reason)


def _enforcement_for(scope_id, rules):
    policy_service = LLMAgentPolicyService()
    if rules:
        policy_service.create(scope_id, "test-policy", rules)
    resolver = LLMAgentPolicyResolver(policy_service)
    return LLMAgentPolicyEnforcement(resolver, LLMAgentPolicyDecisionEngine())


# --- low risk -------------------------------------------------------------


def test_low_risk_action():
    registry = LLMToolRegistryService()
    registry.register("lookup", "Looks things up", SCHEMA)
    enforcement = _enforcement_for(
        "notebook-1", [_rule("allow-lookup", ALLOW, {"tool_name": "lookup"}, "lookup is safe")]
    )
    assessor = LLMAgentPolicyRiskAssessor(enforcement, tool_registry=registry)

    assessment = assessor.assess({"scope_id": "notebook-1", "tool_name": "lookup", "arguments": {}})

    assert isinstance(assessment, RiskAssessment)
    assert assessment.risk_level == LEVEL_LOW
    assert assessment.risk_factors.get("policy_denial", 0) == 0
    assert assessment.risk_factors.get("unregistered_tool", 0) == 0
    assert assessment.risk_factors.get("disabled_tool", 0) == 0


# --- elevated / high risk ---------------------------------------------------


def test_elevated_high_risk_action():
    registry = LLMToolRegistryService()
    registry.register("delete", "Deletes things", SCHEMA, enabled=False)
    enforcement = _enforcement_for("notebook-1", [])
    audit_service = LLMAgentPolicyAuditService()

    denied_decision = LLMAgentPolicyDecisionEngine().decide(
        {"scope_id": "notebook-1", "tool_name": "delete"},
        LLMAgentPolicyResolver(LLMAgentPolicyService()).resolve("notebook-1"),
    )
    audit_service.record("notebook-1", "exec-1", denied_decision)

    assessor = LLMAgentPolicyRiskAssessor(enforcement, audit_service=audit_service, tool_registry=registry)
    assessment = assessor.assess({"scope_id": "notebook-1", "tool_name": "delete", "arguments": {}})

    assert assessment.risk_level == LEVEL_HIGH
    assert assessment.risk_factors["disabled_tool"] == 1
    assert assessment.risk_factors["prior_denied_actions"] == 1


# --- policy-denied action ---------------------------------------------------


def test_policy_denied_action_is_critical_and_authoritative():
    registry = LLMToolRegistryService()
    registry.register("delete", "Deletes things", SCHEMA)
    enforcement = _enforcement_for(
        "notebook-1", [_rule("deny-delete", DENY, {"tool_name": "delete"}, "delete is blocked")]
    )
    assessor = LLMAgentPolicyRiskAssessor(enforcement, tool_registry=registry)

    assessment = assessor.assess({"scope_id": "notebook-1", "tool_name": "delete", "arguments": {}})

    assert assessment.risk_level == LEVEL_CRITICAL
    assert assessment.risk_factors["policy_denial"] == 1
    assert len(assessment.matched_policies) == 1
    assert assessment.matched_policies[0].rule_id == "deny-delete"
    assert "delete is blocked" in assessment.reasons


def test_explicit_denial_outranks_every_other_factor():
    # Even a perfectly registered/enabled tool with no history is still
    # CRITICAL the instant an explicit deny rule matches -- denial is
    # authoritative regardless of what every other factor says.
    registry = LLMToolRegistryService()
    registry.register("delete", "Deletes things", SCHEMA, enabled=True)
    enforcement = _enforcement_for(
        "notebook-1", [_rule("deny-delete", DENY, {"tool_name": "delete"}, "delete is blocked")]
    )
    assessor = LLMAgentPolicyRiskAssessor(enforcement, tool_registry=registry)

    assessment = assessor.assess({"scope_id": "notebook-1", "tool_name": "delete", "arguments": {}})

    assert assessment.risk_level == LEVEL_CRITICAL


# --- multiple risk factors ---------------------------------------------------


def test_multiple_risk_factors_combine():
    enforcement = _enforcement_for("notebook-1", [])
    audit_service = LLMAgentPolicyAuditService()
    resolved = LLMAgentPolicyResolver(LLMAgentPolicyService()).resolve("notebook-1")
    denied_decision = LLMAgentPolicyDecisionEngine().decide(
        {"scope_id": "notebook-1", "tool_name": "unknown-tool"}, resolved
    )
    audit_service.record("notebook-1", "exec-1", denied_decision)
    audit_service.record("notebook-1", "exec-2", denied_decision)

    # no tool_registry given at all: unregistered_tool is simply not
    # evaluated (nothing to check against), only prior_denied_actions
    # and the current (default-deny, non-blocking) policy verdict apply.
    assessor = LLMAgentPolicyRiskAssessor(enforcement, audit_service=audit_service)
    assessment = assessor.assess({"scope_id": "notebook-1", "tool_name": "unknown-tool", "arguments": {}})

    assert "unregistered_tool" not in assessment.risk_factors
    assert assessment.risk_factors["prior_denied_actions"] == 2
    assert len(assessment.matched_security_findings) == 2

    # Now add a real tool_registry so a second, independent factor
    # (unregistered_tool) also contributes alongside prior_denied_actions.
    registry = LLMToolRegistryService()
    assessor_with_registry = LLMAgentPolicyRiskAssessor(
        enforcement, audit_service=audit_service, tool_registry=registry
    )
    combined = assessor_with_registry.assess(
        {"scope_id": "notebook-1", "tool_name": "unknown-tool", "arguments": {}}
    )

    assert combined.risk_factors["unregistered_tool"] == 1
    assert combined.risk_factors["prior_denied_actions"] == 2
    assert len(combined.risk_factors) >= 2


# --- missing context ---------------------------------------------------


def test_missing_context_degrades_gracefully():
    # No tool_registry, no audit_service, and action_context names no
    # tool_name at all -- every optional factor is simply omitted, never
    # guessed, and assess() never raises.
    enforcement = _enforcement_for("notebook-1", [])
    assessor = LLMAgentPolicyRiskAssessor(enforcement)

    assessment = assessor.assess({"scope_id": "notebook-1"})

    assert assessment.risk_level == LEVEL_LOW
    assert "unregistered_tool" not in assessment.risk_factors
    assert "disabled_tool" not in assessment.risk_factors
    assert "prior_denied_actions" not in assessment.risk_factors
    assert assessment.provenance["tool_status"] is None
    assert assessment.provenance["prior_denied_actions"] is None


def test_missing_scope_fails_closed_as_critical():
    # An action_context that cannot even be resolved (no scope_id) must
    # never read as low risk -- the same fail-closed discipline
    # LLMAgentPolicyEnforcedExecutionService already applies.
    enforcement = _enforcement_for("notebook-1", [])
    assessor = LLMAgentPolicyRiskAssessor(enforcement)

    assessment = assessor.assess({"tool_name": "lookup"})

    assert assessment.risk_level == LEVEL_CRITICAL
    assert assessment.risk_factors["policy_evaluation_failed"] == 1
    assert assessment.provenance["policy_decision"] is None
    assert assessment.provenance["policy_evaluation_error"]


def test_invalid_action_context_raises():
    enforcement = _enforcement_for("notebook-1", [])
    assessor = LLMAgentPolicyRiskAssessor(enforcement)

    with pytest.raises(InvalidActionContextError):
        assessor.assess("not-a-dict")


# --- deterministic assessment ---------------------------------------------------


def test_deterministic_assessment():
    registry = LLMToolRegistryService()
    registry.register("delete", "Deletes things", SCHEMA, enabled=False)
    enforcement = _enforcement_for("notebook-1", [])
    audit_service = LLMAgentPolicyAuditService()
    resolved = LLMAgentPolicyResolver(LLMAgentPolicyService()).resolve("notebook-1")
    denied_decision = LLMAgentPolicyDecisionEngine().decide(
        {"scope_id": "notebook-1", "tool_name": "delete"}, resolved
    )
    audit_service.record("notebook-1", "exec-1", denied_decision)

    assessor = LLMAgentPolicyRiskAssessor(enforcement, audit_service=audit_service, tool_registry=registry)
    action_context = {"scope_id": "notebook-1", "tool_name": "delete", "arguments": {}}

    first = assessor.assess(action_context)
    second = assessor.assess(action_context)

    assert first == second


# --- provenance ---------------------------------------------------


def test_provenance_traces_every_field():
    registry = LLMToolRegistryService()
    registry.register("delete", "Deletes things", SCHEMA)
    enforcement = _enforcement_for(
        "notebook-1", [_rule("deny-delete", DENY, {"tool_name": "delete"}, "delete is blocked")]
    )
    audit_service = LLMAgentPolicyAuditService()
    assessor = LLMAgentPolicyRiskAssessor(enforcement, audit_service=audit_service, tool_registry=registry)

    action_context = {"scope_id": "notebook-1", "tool_name": "delete", "arguments": {"id": 1}}
    assessment = assessor.assess(action_context)

    assert assessment.provenance["action_context"] == action_context
    # a defensive copy, not the same object
    assert assessment.provenance["action_context"] is not action_context

    decision = assessment.provenance["policy_decision"]
    assert decision.decision == DENY
    assert decision.matched_rules[0].rule_id == "deny-delete"
    # provenance carries the full evaluation trail, not just the winner
    assert len(decision.provenance) == 1

    assert assessment.provenance["tool_status"] == {
        "tool_name": "delete",
        "registered": True,
        "enabled": True,
    }
    assert assessment.provenance["prior_denied_actions"] == []
