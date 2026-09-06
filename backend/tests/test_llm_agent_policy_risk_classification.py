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
    LEVEL_MEDIUM,
    LLMAgentPolicyRiskAssessor,
    RiskAssessment,
)
from backend.agent_policy_risk_classification import (
    CONFIDENCE_HIGH,
    CONFIDENCE_LOW,
    CONFIDENCE_MEDIUM,
    InvalidRiskAssessmentError,
    LLMAgentPolicyRiskClassifier,
    RiskClassification,
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


def _bare_assessment(risk_level, provenance=None):
    return RiskAssessment(
        risk_level=risk_level,
        risk_factors={},
        matched_policies=[],
        matched_security_findings=[],
        reasons=["synthetic"],
        provenance=provenance if provenance is not None else {"policy_decision": object()},
    )


# --- each supported severity ---------------------------------------------


def test_classifies_low_severity():
    registry = LLMToolRegistryService()
    registry.register("lookup", "Looks things up", SCHEMA)
    enforcement = _enforcement_for(
        "notebook-1", [_rule("allow-lookup", ALLOW, {"tool_name": "lookup"})]
    )
    assessment = LLMAgentPolicyRiskAssessor(enforcement, tool_registry=registry).assess(
        {"scope_id": "notebook-1", "tool_name": "lookup", "arguments": {}}
    )
    assert assessment.risk_level == LEVEL_LOW  # sanity

    classification = LLMAgentPolicyRiskClassifier().classify(assessment)

    assert isinstance(classification, RiskClassification)
    assert classification.risk_level == LEVEL_LOW


def test_classifies_medium_severity():
    registry = LLMToolRegistryService()
    enforcement = _enforcement_for("notebook-1", [])
    assessment = LLMAgentPolicyRiskAssessor(enforcement, tool_registry=registry).assess(
        {"scope_id": "notebook-1", "tool_name": "unknown-tool", "arguments": {}}
    )
    assert assessment.risk_level == LEVEL_MEDIUM  # sanity: unregistered_tool alone == 30

    classification = LLMAgentPolicyRiskClassifier().classify(assessment)
    assert classification.risk_level == LEVEL_MEDIUM


def test_classifies_high_severity():
    registry = LLMToolRegistryService()
    registry.register("delete", "Deletes things", SCHEMA, enabled=False)
    enforcement = _enforcement_for("notebook-1", [])
    audit_service = LLMAgentPolicyAuditService()
    resolved = LLMAgentPolicyResolver(LLMAgentPolicyService()).resolve("notebook-1")
    denied = LLMAgentPolicyDecisionEngine().decide({"scope_id": "notebook-1", "tool_name": "delete"}, resolved)
    audit_service.record("notebook-1", "exec-1", denied)

    assessment = LLMAgentPolicyRiskAssessor(
        enforcement, audit_service=audit_service, tool_registry=registry
    ).assess({"scope_id": "notebook-1", "tool_name": "delete", "arguments": {}})
    assert assessment.risk_level == LEVEL_HIGH  # sanity: disabled(40) + 1 prior denial(15) == 55

    classification = LLMAgentPolicyRiskClassifier().classify(assessment)
    assert classification.risk_level == LEVEL_HIGH


def test_classifies_critical_severity():
    enforcement = _enforcement_for(
        "notebook-1", [_rule("deny-delete", DENY, {"tool_name": "delete"}, "delete is blocked")]
    )
    assessment = LLMAgentPolicyRiskAssessor(enforcement).assess(
        {"scope_id": "notebook-1", "tool_name": "delete", "arguments": {}}
    )
    assert assessment.risk_level == LEVEL_CRITICAL  # sanity

    classification = LLMAgentPolicyRiskClassifier().classify(assessment)
    assert classification.risk_level == LEVEL_CRITICAL
    # explicit denial's own reasons are preserved through classification
    assert any("delete is blocked" in reason for reason in classification.reasons)


# --- threshold boundaries (confidence evidence-completeness) ---------------


def test_confidence_boundary_no_optional_evidence_is_low():
    assessment = _bare_assessment(
        LEVEL_LOW, provenance={"policy_decision": object(), "tool_status": None, "prior_denied_actions": None}
    )
    classification = LLMAgentPolicyRiskClassifier().classify(assessment)
    assert classification.confidence == CONFIDENCE_LOW
    assert classification.evidence == {
        "policy_decision": True,
        "tool_status": False,
        "prior_denied_actions": False,
    }


def test_confidence_boundary_one_optional_evidence_is_medium():
    assessment = _bare_assessment(
        LEVEL_LOW,
        provenance={"policy_decision": object(), "tool_status": {"tool_name": "x"}, "prior_denied_actions": None},
    )
    classification = LLMAgentPolicyRiskClassifier().classify(assessment)
    assert classification.confidence == CONFIDENCE_MEDIUM


def test_confidence_boundary_both_optional_evidence_is_high():
    assessment = _bare_assessment(
        LEVEL_LOW,
        provenance={
            "policy_decision": object(),
            "tool_status": {"tool_name": "x"},
            "prior_denied_actions": [],
        },
    )
    classification = LLMAgentPolicyRiskClassifier().classify(assessment)
    assert classification.confidence == CONFIDENCE_HIGH


def test_confidence_is_low_when_policy_decision_missing_regardless_of_other_evidence():
    # A failed policy evaluation (Commit #1's own fail-closed path) means
    # LOW confidence even when the other two sources are fully present --
    # missing the one authoritative signal can never be offset.
    assessment = _bare_assessment(
        LEVEL_CRITICAL,
        provenance={
            "policy_decision": None,
            "tool_status": {"tool_name": "x"},
            "prior_denied_actions": [],
        },
    )
    classification = LLMAgentPolicyRiskClassifier().classify(assessment)
    assert classification.confidence == CONFIDENCE_LOW


# --- multiple factors -------------------------------------------------------


def test_multiple_risk_factors_are_preserved_verbatim():
    registry = LLMToolRegistryService()
    registry.register("delete", "Deletes things", SCHEMA, enabled=False)
    enforcement = _enforcement_for("notebook-1", [])
    audit_service = LLMAgentPolicyAuditService()
    resolved = LLMAgentPolicyResolver(LLMAgentPolicyService()).resolve("notebook-1")
    denied = LLMAgentPolicyDecisionEngine().decide({"scope_id": "notebook-1", "tool_name": "delete"}, resolved)
    audit_service.record("notebook-1", "exec-1", denied)
    audit_service.record("notebook-1", "exec-2", denied)

    assessment = LLMAgentPolicyRiskAssessor(
        enforcement, audit_service=audit_service, tool_registry=registry
    ).assess({"scope_id": "notebook-1", "tool_name": "delete", "arguments": {}})

    classification = LLMAgentPolicyRiskClassifier().classify(assessment)

    assert classification.risk_factors == assessment.risk_factors
    assert classification.risk_factors["disabled_tool"] == 1
    assert classification.risk_factors["prior_denied_actions"] == 2
    # classify() never mutates the source risk_factors mapping
    assert classification.risk_factors is not assessment.risk_factors


# --- missing / invalid assessment ------------------------------------------


def test_rejects_non_risk_assessment_input():
    with pytest.raises(InvalidRiskAssessmentError):
        LLMAgentPolicyRiskClassifier().classify({"risk_level": "LOW"})

    with pytest.raises(InvalidRiskAssessmentError):
        LLMAgentPolicyRiskClassifier().classify(None)


def test_rejects_assessment_with_corrupted_risk_level():
    assessment = _bare_assessment("NOT-A-REAL-LEVEL")
    with pytest.raises(InvalidRiskAssessmentError):
        LLMAgentPolicyRiskClassifier().classify(assessment)


# --- deterministic classification -------------------------------------------


def test_deterministic_classification():
    registry = LLMToolRegistryService()
    registry.register("delete", "Deletes things", SCHEMA, enabled=False)
    enforcement = _enforcement_for("notebook-1", [])
    assessment = LLMAgentPolicyRiskAssessor(enforcement, tool_registry=registry).assess(
        {"scope_id": "notebook-1", "tool_name": "delete", "arguments": {}}
    )

    classifier = LLMAgentPolicyRiskClassifier()
    first = classifier.classify(assessment)
    second = classifier.classify(assessment)

    assert first == second


# --- provenance --------------------------------------------------------------


def test_provenance_embeds_the_full_assessment():
    registry = LLMToolRegistryService()
    registry.register("lookup", "Looks things up", SCHEMA)
    enforcement = _enforcement_for(
        "notebook-1", [_rule("allow-lookup", ALLOW, {"tool_name": "lookup"})]
    )
    assessment = LLMAgentPolicyRiskAssessor(enforcement, tool_registry=registry).assess(
        {"scope_id": "notebook-1", "tool_name": "lookup", "arguments": {}}
    )

    classification = LLMAgentPolicyRiskClassifier().classify(assessment)

    assert classification.provenance["assessment"] is assessment
    assert classification.provenance["evidence_availability"] == classification.evidence
