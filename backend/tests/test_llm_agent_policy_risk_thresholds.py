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
    LLMAgentPolicyRiskAssessor,
)
from backend.agent_policy_risk_classification import LLMAgentPolicyRiskClassifier, RiskClassification
from backend.agent_policy_risk_thresholds import (
    ACTIONS,
    DEFAULT_DENY_AT,
    DEFAULT_REVIEW_AT,
    REVIEW,
    InvalidRiskClassificationError,
    InvalidRiskThresholdsError,
    JsonRiskThresholdsStore,
    LLMAgentPolicyRiskThresholdService,
    RiskAction,
    RiskThresholds,
)
from backend.llm.tools import LLMToolRegistryService

SCHEMA = {"type": "object", "properties": {}, "required": []}


def _rule(rule_id, effect, match=None, reason=""):
    return LLMAgentPolicyRule(rule_id=rule_id, effect=effect, match=match or {}, reason=reason)


def _classification(risk_level, provenance=None):
    return RiskClassification(
        risk_level=risk_level,
        confidence="HIGH",
        evidence={"policy_decision": True, "tool_status": True, "prior_denied_actions": True},
        risk_factors={},
        reasons=["synthetic"],
        provenance=provenance or {},
    )


def _denied_classification(scope_id="notebook-1", tool_name="delete"):
    policy_service = LLMAgentPolicyService()
    policy_service.create(scope_id, "deny-policy", [_rule("deny", POLICY_DENY, {"tool_name": tool_name})])
    resolver = LLMAgentPolicyResolver(policy_service)
    enforcement = LLMAgentPolicyEnforcement(resolver, LLMAgentPolicyDecisionEngine())
    assessment = LLMAgentPolicyRiskAssessor(enforcement).assess(
        {"scope_id": scope_id, "tool_name": tool_name, "arguments": {}}
    )
    return LLMAgentPolicyRiskClassifier().classify(assessment)


# --- default thresholds -----------------------------------------------------


def test_default_thresholds():
    service = LLMAgentPolicyRiskThresholdService()

    thresholds = service.get("notebook-1")

    assert isinstance(thresholds, RiskThresholds)
    assert thresholds.scope_id == "notebook-1"
    assert thresholds.review_at == DEFAULT_REVIEW_AT == LEVEL_HIGH
    assert thresholds.deny_at == DEFAULT_DENY_AT == LEVEL_CRITICAL


def test_default_thresholds_are_not_silently_persisted():
    service = LLMAgentPolicyRiskThresholdService()
    service.get("notebook-1")

    assert service.store.get("notebook-1") is None


# --- custom thresholds -------------------------------------------------------


def test_custom_thresholds_round_trip():
    service = LLMAgentPolicyRiskThresholdService()

    saved = service.set("notebook-1", {"review_at": LEVEL_MEDIUM, "deny_at": LEVEL_HIGH})

    assert saved.review_at == LEVEL_MEDIUM
    assert saved.deny_at == LEVEL_HIGH
    fetched = service.get("notebook-1")
    assert fetched.review_at == LEVEL_MEDIUM
    assert fetched.deny_at == LEVEL_HIGH


def test_set_accepts_a_risk_thresholds_instance():
    service = LLMAgentPolicyRiskThresholdService()
    custom = RiskThresholds(scope_id="ignored", review_at=LEVEL_LOW, deny_at=LEVEL_MEDIUM)

    saved = service.set("notebook-1", custom)

    # the service's own scope_id always wins, never the input's
    assert saved.scope_id == "notebook-1"
    assert saved.review_at == LEVEL_LOW
    assert saved.deny_at == LEVEL_MEDIUM


# --- boundary values ---------------------------------------------------------


def test_boundary_exactly_at_review_at_triggers_review():
    service = LLMAgentPolicyRiskThresholdService()
    service.set("notebook-1", {"review_at": LEVEL_MEDIUM, "deny_at": LEVEL_CRITICAL})

    action = service.evaluate("notebook-1", _classification(LEVEL_MEDIUM))
    assert action.action == REVIEW


def test_boundary_just_below_review_at_is_allow():
    service = LLMAgentPolicyRiskThresholdService()
    service.set("notebook-1", {"review_at": LEVEL_MEDIUM, "deny_at": LEVEL_CRITICAL})

    action = service.evaluate("notebook-1", _classification(LEVEL_LOW))
    assert action.action == POLICY_ALLOW


def test_boundary_exactly_at_deny_at_triggers_deny():
    service = LLMAgentPolicyRiskThresholdService()
    service.set("notebook-1", {"review_at": LEVEL_MEDIUM, "deny_at": LEVEL_HIGH})

    action = service.evaluate("notebook-1", _classification(LEVEL_HIGH))
    assert action.action == POLICY_DENY


def test_boundary_review_and_deny_can_coincide():
    # a valid, if aggressive, configuration: everything at or above HIGH
    # is denied outright, with no separate review band
    service = LLMAgentPolicyRiskThresholdService()
    service.set("notebook-1", {"review_at": LEVEL_HIGH, "deny_at": LEVEL_HIGH})

    assert service.evaluate("notebook-1", _classification(LEVEL_HIGH)).action == POLICY_DENY
    assert service.evaluate("notebook-1", _classification(LEVEL_MEDIUM)).action == POLICY_ALLOW


# --- invalid ordering ---------------------------------------------------------


def test_invalid_ordering_rejected_by_model():
    with pytest.raises(InvalidRiskThresholdsError):
        RiskThresholds(scope_id="notebook-1", review_at=LEVEL_HIGH, deny_at=LEVEL_MEDIUM)


def test_invalid_ordering_rejected_by_service_set():
    service = LLMAgentPolicyRiskThresholdService()
    with pytest.raises(InvalidRiskThresholdsError):
        service.set("notebook-1", {"review_at": LEVEL_CRITICAL, "deny_at": LEVEL_LOW})

    # a rejected set() never partially persists
    assert service.store.get("notebook-1") is None


def test_invalid_level_name_rejected():
    with pytest.raises(InvalidRiskThresholdsError):
        RiskThresholds(scope_id="notebook-1", review_at="NOT-A-LEVEL", deny_at=LEVEL_CRITICAL)


# --- scope isolation -----------------------------------------------------------


def test_scope_isolation():
    service = LLMAgentPolicyRiskThresholdService()
    service.set("notebook-1", {"review_at": LEVEL_LOW, "deny_at": LEVEL_MEDIUM})
    service.set("notebook-2", {"review_at": LEVEL_HIGH, "deny_at": LEVEL_CRITICAL})

    assert service.get("notebook-1").review_at == LEVEL_LOW
    assert service.get("notebook-2").review_at == LEVEL_HIGH

    # a scope that was never configured keeps the plain default,
    # unaffected by any other scope's configuration
    assert service.get("notebook-3").review_at == DEFAULT_REVIEW_AT


# --- allow/review/deny mapping --------------------------------------------------


def test_default_mapping_across_all_levels():
    service = LLMAgentPolicyRiskThresholdService()

    assert service.evaluate("notebook-1", _classification(LEVEL_LOW)).action == POLICY_ALLOW
    assert service.evaluate("notebook-1", _classification(LEVEL_MEDIUM)).action == POLICY_ALLOW
    assert service.evaluate("notebook-1", _classification(LEVEL_HIGH)).action == REVIEW
    assert service.evaluate("notebook-1", _classification(LEVEL_CRITICAL)).action == POLICY_DENY
    assert set(ACTIONS) == {POLICY_ALLOW, REVIEW, POLICY_DENY}


def test_evaluate_returns_a_risk_action_with_provenance():
    service = LLMAgentPolicyRiskThresholdService()
    classification = _classification(LEVEL_HIGH)

    action = service.evaluate("notebook-1", classification)

    assert isinstance(action, RiskAction)
    assert action.scope_id == "notebook-1"
    assert action.risk_level == LEVEL_HIGH
    assert action.provenance["classification"] is classification
    assert action.provenance["thresholds"] == service.get("notebook-1")


def test_evaluate_never_mutates_the_classification():
    service = LLMAgentPolicyRiskThresholdService()
    classification = _classification(LEVEL_CRITICAL)
    before = RiskClassification(**vars(classification))

    service.evaluate("notebook-1", classification)

    assert classification == before


def test_explicit_policy_denial_is_always_deny_even_under_lenient_thresholds():
    # the most lenient valid configuration short of turning deny off
    # entirely: review and deny both pinned to CRITICAL
    service = LLMAgentPolicyRiskThresholdService()
    service.set("notebook-1", {"review_at": LEVEL_CRITICAL, "deny_at": LEVEL_CRITICAL})

    classification = _denied_classification("notebook-1")
    assert classification.risk_level == LEVEL_CRITICAL  # sanity

    action = service.evaluate("notebook-1", classification)
    assert action.action == POLICY_DENY


def test_evaluate_rejects_invalid_classification():
    service = LLMAgentPolicyRiskThresholdService()
    with pytest.raises(InvalidRiskClassificationError):
        service.evaluate("notebook-1", "not-a-classification")


# --- persistence ---------------------------------------------------------------


def test_persistence_across_service_instances_sharing_a_store():
    from backend.agent_policy_risk_thresholds import InMemoryRiskThresholdsStore

    shared_store = InMemoryRiskThresholdsStore()
    writer = LLMAgentPolicyRiskThresholdService(store=shared_store)
    writer.set("notebook-1", {"review_at": LEVEL_LOW, "deny_at": LEVEL_MEDIUM})

    reader = LLMAgentPolicyRiskThresholdService(store=shared_store)
    fetched = reader.get("notebook-1")

    assert fetched.review_at == LEVEL_LOW
    assert fetched.deny_at == LEVEL_MEDIUM


def test_persistence_through_json_store(tmp_path):
    path = tmp_path / "risk_thresholds.json"
    writer = LLMAgentPolicyRiskThresholdService(store=JsonRiskThresholdsStore(path))
    writer.set("notebook-1", {"review_at": LEVEL_MEDIUM, "deny_at": LEVEL_HIGH})

    reloaded = LLMAgentPolicyRiskThresholdService(store=JsonRiskThresholdsStore(path))
    fetched = reloaded.get("notebook-1")

    assert fetched.scope_id == "notebook-1"
    assert fetched.review_at == LEVEL_MEDIUM
    assert fetched.deny_at == LEVEL_HIGH
