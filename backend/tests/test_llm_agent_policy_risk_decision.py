import pytest

from backend.agent_policy_decision import LLMAgentPolicyDecisionEngine
from backend.agent_policy_engine import ALLOW as POLICY_ALLOW
from backend.agent_policy_engine import DENY as POLICY_DENY
from backend.agent_policy_engine import LLMAgentPolicyRule, LLMAgentPolicyService
from backend.agent_policy_enforcement import LLMAgentPolicyEnforcement
from backend.agent_policy_resolution import LLMAgentPolicyResolver
from backend.agent_policy_risk_assessment import (
    LEVEL_CRITICAL,
    LEVEL_HIGH,
    LEVEL_LOW,
    LEVEL_MEDIUM,
    InvalidActionContextError,
    LLMAgentPolicyRiskAssessor,
)
from backend.agent_policy_risk_classification import LLMAgentPolicyRiskClassifier, RiskClassification
from backend.agent_policy_risk_decision import LLMAgentPolicyRiskDecisionEngine, RiskDecision
from backend.agent_policy_risk_thresholds import (
    REVIEW,
    InvalidRiskClassificationError,
    InvalidRiskThresholdsError,
    RiskThresholds,
)
from backend.llm.tools import LLMToolRegistryService

SCHEMA = {"type": "object", "properties": {}, "required": []}


def _rule(rule_id, effect, match=None, reason=""):
    return LLMAgentPolicyRule(rule_id=rule_id, effect=effect, match=match or {}, reason=reason)


def _classification(risk_level, risk_factors=None, reasons=None):
    return RiskClassification(
        risk_level=risk_level,
        confidence="HIGH",
        evidence={},
        risk_factors=risk_factors or {},
        reasons=reasons or ["synthetic"],
        provenance={},
    )


def _real_classification(scope_id, tool_name, tool_registry=None, rules=None):
    policy_service = LLMAgentPolicyService()
    if rules:
        policy_service.create(scope_id, "test-policy", rules)
    resolver = LLMAgentPolicyResolver(policy_service)
    enforcement = LLMAgentPolicyEnforcement(resolver, LLMAgentPolicyDecisionEngine())
    assessment = LLMAgentPolicyRiskAssessor(enforcement, tool_registry=tool_registry).assess(
        {"scope_id": scope_id, "tool_name": tool_name, "arguments": {}}
    )
    return LLMAgentPolicyRiskClassifier().classify(assessment)


ACTION_CONTEXT = {"scope_id": "notebook-1", "tool_name": "delete", "arguments": {}}


# --- allow/review/deny thresholds -------------------------------------------


def test_allow_under_default_thresholds():
    classification = _classification(LEVEL_LOW)
    decision = LLMAgentPolicyRiskDecisionEngine().decide(ACTION_CONTEXT, classification)
    assert decision.decision == POLICY_ALLOW


def test_review_under_default_thresholds():
    classification = _classification(LEVEL_HIGH)
    decision = LLMAgentPolicyRiskDecisionEngine().decide(ACTION_CONTEXT, classification)
    assert decision.decision == REVIEW


def test_deny_under_default_thresholds():
    classification = _classification(LEVEL_CRITICAL)
    decision = LLMAgentPolicyRiskDecisionEngine().decide(ACTION_CONTEXT, classification)
    assert decision.decision == POLICY_DENY


def test_custom_thresholds_change_the_mapping():
    thresholds = RiskThresholds(scope_id="notebook-1", review_at=LEVEL_LOW, deny_at=LEVEL_MEDIUM)
    classification = _classification(LEVEL_LOW)

    decision = LLMAgentPolicyRiskDecisionEngine().decide(ACTION_CONTEXT, classification, thresholds)
    assert decision.decision == REVIEW  # would be ALLOW under defaults


# --- policy-denied action ----------------------------------------------------


def test_real_policy_denial_is_deny_end_to_end():
    classification = _real_classification(
        "notebook-1", "delete", rules=[_rule("deny-delete", POLICY_DENY, {"tool_name": "delete"}, "blocked")]
    )
    assert classification.risk_level == LEVEL_CRITICAL  # sanity

    lenient = RiskThresholds(scope_id="notebook-1", review_at=LEVEL_CRITICAL, deny_at=LEVEL_CRITICAL)
    decision = LLMAgentPolicyRiskDecisionEngine().decide(ACTION_CONTEXT, classification, lenient)

    assert decision.decision == POLICY_DENY
    assert any("blocked" in reason for reason in decision.reasons)


def test_policy_denial_overrides_even_a_corrupted_low_risk_level():
    # a hand-built, internally-inconsistent classification: risk_factors
    # says an explicit policy denial happened, but risk_level claims LOW.
    # decide() must never let a mismatched risk_level silently downgrade
    # a real denial.
    classification = _classification(LEVEL_LOW, risk_factors={"policy_denial": 1})
    thresholds = RiskThresholds(scope_id="notebook-1", review_at=LEVEL_HIGH, deny_at=LEVEL_CRITICAL)

    decision = LLMAgentPolicyRiskDecisionEngine().decide(ACTION_CONTEXT, classification, thresholds)

    assert decision.decision == POLICY_DENY
    assert any("overrides" in reason for reason in decision.reasons)


# --- boundary values ----------------------------------------------------------


def test_boundary_exactly_at_review_at():
    thresholds = RiskThresholds(scope_id="notebook-1", review_at=LEVEL_MEDIUM, deny_at=LEVEL_CRITICAL)
    decision = LLMAgentPolicyRiskDecisionEngine().decide(
        ACTION_CONTEXT, _classification(LEVEL_MEDIUM), thresholds
    )
    assert decision.decision == REVIEW


def test_boundary_just_below_review_at():
    thresholds = RiskThresholds(scope_id="notebook-1", review_at=LEVEL_MEDIUM, deny_at=LEVEL_CRITICAL)
    decision = LLMAgentPolicyRiskDecisionEngine().decide(
        ACTION_CONTEXT, _classification(LEVEL_LOW), thresholds
    )
    assert decision.decision == POLICY_ALLOW


def test_boundary_exactly_at_deny_at():
    thresholds = RiskThresholds(scope_id="notebook-1", review_at=LEVEL_MEDIUM, deny_at=LEVEL_HIGH)
    decision = LLMAgentPolicyRiskDecisionEngine().decide(
        ACTION_CONTEXT, _classification(LEVEL_HIGH), thresholds
    )
    assert decision.decision == POLICY_DENY


# --- multiple risk factors ----------------------------------------------------


def test_multiple_risk_factors_are_preserved():
    registry = LLMToolRegistryService()
    registry.register("delete", "Deletes things", SCHEMA, enabled=False)
    classification = _real_classification("notebook-1", "delete", tool_registry=registry)

    decision = LLMAgentPolicyRiskDecisionEngine().decide(ACTION_CONTEXT, classification)

    assert decision.risk_factors == classification.risk_factors
    assert decision.risk_factors["disabled_tool"] == 1
    assert decision.risk_factors is not classification.risk_factors


# --- missing thresholds --------------------------------------------------------


def test_missing_thresholds_falls_back_to_defaults():
    decision_high = LLMAgentPolicyRiskDecisionEngine().decide(
        ACTION_CONTEXT, _classification(LEVEL_HIGH), thresholds=None
    )
    decision_critical = LLMAgentPolicyRiskDecisionEngine().decide(
        ACTION_CONTEXT, _classification(LEVEL_CRITICAL), thresholds=None
    )

    assert decision_high.decision == REVIEW
    assert decision_critical.decision == POLICY_DENY
    assert decision_high.provenance["thresholds"] is None


def test_invalid_thresholds_type_rejected():
    with pytest.raises(InvalidRiskThresholdsError):
        LLMAgentPolicyRiskDecisionEngine().decide(
            ACTION_CONTEXT, _classification(LEVEL_LOW), thresholds="not-thresholds"
        )


# --- provenance -----------------------------------------------------------------


def test_provenance_embeds_every_input_verbatim():
    classification = _classification(LEVEL_MEDIUM)
    thresholds = RiskThresholds(scope_id="notebook-1")

    decision = LLMAgentPolicyRiskDecisionEngine().decide(ACTION_CONTEXT, classification, thresholds)

    assert decision.provenance["action_context"] == ACTION_CONTEXT
    assert decision.provenance["action_context"] is not ACTION_CONTEXT
    assert decision.provenance["classification"] is classification
    assert decision.provenance["thresholds"] is thresholds


# --- deterministic decisions ------------------------------------------------------


def test_deterministic_decisions():
    classification = _classification(LEVEL_HIGH)
    thresholds = RiskThresholds(scope_id="notebook-1")
    engine = LLMAgentPolicyRiskDecisionEngine()

    first = engine.decide(ACTION_CONTEXT, classification, thresholds)
    second = engine.decide(ACTION_CONTEXT, classification, thresholds)

    assert first == second


# --- invalid input -----------------------------------------------------------------


def test_invalid_action_context_rejected():
    with pytest.raises(InvalidActionContextError):
        LLMAgentPolicyRiskDecisionEngine().decide("not-a-dict", _classification(LEVEL_LOW))


def test_invalid_classification_rejected():
    with pytest.raises(InvalidRiskClassificationError):
        LLMAgentPolicyRiskDecisionEngine().decide(ACTION_CONTEXT, "not-a-classification")


def test_returns_a_risk_decision_instance():
    decision = LLMAgentPolicyRiskDecisionEngine().decide(ACTION_CONTEXT, _classification(LEVEL_LOW))
    assert isinstance(decision, RiskDecision)
