import pytest

from backend.agent_policy_decision import LLMAgentPolicyDecisionEngine
from backend.agent_policy_engine import ALLOW as POLICY_ALLOW
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
from backend.agent_policy_engine import ALLOW, DENY
from backend.agent_policy_risk_thresholds import (
    REVIEW,
    LLMAgentPolicyRiskThresholdService,
    RiskThresholds,
)
from backend.agent_risk_profile import LLMAgentRiskProfile, LLMAgentRiskProfileService, RiskProfileActionRule
from backend.agent_risk_profile_simulation import (
    InvalidRiskProfileSimulationError,
    LLMAgentRiskProfileSimulator,
    RiskSimulationResult,
)


def _rule(rule_id, level, match=None, reason=""):
    return RiskProfileActionRule(rule_id=rule_id, match=match or {}, level=level, reason=reason)


def _profile(**overrides):
    defaults = dict(scope_id="scope-1", name="p1", default_level=LEVEL_LOW)
    defaults.update(overrides)
    return LLMAgentRiskProfile(**defaults)


def _real_assessor(scope_id="scope-1", tool_name="lookup", deny_tool=None):
    policy_service = LLMAgentPolicyService()
    rules = [LLMAgentPolicyRule(rule_id="allow-all", effect=POLICY_ALLOW, match={})]
    policy_service.create(scope_id, "allow-all-policy", rules)
    resolver = LLMAgentPolicyResolver(policy_service)
    enforcement = LLMAgentPolicyEnforcement(resolver, LLMAgentPolicyDecisionEngine())
    return LLMAgentPolicyRiskAssessor(enforcement)


# --- low/medium/high/critical scenarios --------------------------------


@pytest.mark.parametrize("level", [LEVEL_LOW, LEVEL_MEDIUM, LEVEL_HIGH, LEVEL_CRITICAL])
def test_simulate_reports_the_matched_rule_level(level):
    simulator = LLMAgentRiskProfileSimulator()
    profile = _profile(action_rules=[_rule("r1", level, {"tool_name": "delete_file"})], default_level=LEVEL_LOW)

    result = simulator.simulate(profile, {"tool_name": "delete_file"})
    assert isinstance(result, RiskSimulationResult)
    assert result.risk_level == level


def test_simulate_falls_back_to_default_level_when_nothing_matches():
    simulator = LLMAgentRiskProfileSimulator()
    profile = _profile(action_rules=[_rule("r1", LEVEL_CRITICAL, {"tool_name": "delete_file"})], default_level=LEVEL_MEDIUM)

    result = simulator.simulate(profile, {"tool_name": "read_file"})
    assert result.risk_level == LEVEL_MEDIUM
    assert result.matched_rule_id is None


# --- matching profile rules --------------------------------------------


def test_matched_rules_lists_every_satisfied_rule():
    simulator = LLMAgentRiskProfileSimulator()
    profile = _profile(
        action_rules=[
            _rule("r1", LEVEL_HIGH, {"subject": "prod"}),
            _rule("r2", LEVEL_HIGH, {"tool_name": "delete_file"}),
            _rule("r3", LEVEL_LOW, {"tool_name": "read_file"}),
        ]
    )

    result = simulator.simulate(profile, {"tool_name": "delete_file", "subject": "prod"})
    assert set(result.matched_rules) == {"r1", "r2"}
    assert result.matched_rule_id == "r1"  # first-in-list-order wins, same as production


# --- threshold interaction -----------------------------------------------


def test_default_thresholds_used_when_no_threshold_service_configured():
    simulator = LLMAgentRiskProfileSimulator()
    profile = _profile(action_rules=[_rule("r1", LEVEL_HIGH, {"tool_name": "delete_file"})])

    result = simulator.simulate(profile, {"tool_name": "delete_file"})
    assert result.action == REVIEW  # DEFAULT_REVIEW_AT == HIGH


def test_custom_thresholds_change_the_action_result():
    threshold_service = LLMAgentPolicyRiskThresholdService()
    threshold_service.set("scope-1", RiskThresholds(scope_id="scope-1", review_at=LEVEL_MEDIUM, deny_at=LEVEL_HIGH))
    simulator = LLMAgentRiskProfileSimulator(threshold_service=threshold_service)
    profile = _profile(action_rules=[_rule("r1", LEVEL_HIGH, {"tool_name": "delete_file"})])

    result = simulator.simulate(profile, {"tool_name": "delete_file"})
    assert result.action == DENY


def test_low_risk_allows_by_default():
    simulator = LLMAgentRiskProfileSimulator()
    profile = _profile(default_level=LEVEL_LOW)

    result = simulator.simulate(profile, {"tool_name": "read_file"})
    assert result.action == ALLOW


# --- conflicting rules -------------------------------------------------


def test_conflicting_action_rules_are_surfaced_not_hidden():
    simulator = LLMAgentRiskProfileSimulator()
    profile = _profile(
        action_rules=[
            _rule("r1", LEVEL_LOW, {"tool_name": "delete_file"}),
            _rule("r2", LEVEL_CRITICAL, {"tool_name": "delete_file"}),
        ]
    )

    result = simulator.simulate(profile, {"tool_name": "delete_file"})
    # production resolution still deterministically picks the first match --
    assert result.risk_level == LEVEL_LOW
    assert result.matched_rule_id == "r1"
    # but the disagreement is surfaced, not silently swallowed
    conflict = next(c for c in result.conflicts if c["type"] == "conflicting_action_rules")
    assert set(conflict["matched_rule_ids"]) == {"r1", "r2"}
    assert conflict["levels"] == sorted({LEVEL_LOW, LEVEL_CRITICAL})
    assert any("differing levels" in reason for reason in result.reasons)


def test_no_conflict_reported_when_rules_agree():
    simulator = LLMAgentRiskProfileSimulator()
    profile = _profile(
        action_rules=[
            _rule("r1", LEVEL_HIGH, {"tool_name": "delete_file"}),
            _rule("r2", LEVEL_HIGH, {"subject": "prod"}),
        ]
    )

    result = simulator.simulate(profile, {"tool_name": "delete_file", "subject": "prod"})
    assert result.conflicts == []


def test_profile_assessment_disagreement_surfaced_as_conflict():
    assessor = _real_assessor()
    simulator = LLMAgentRiskProfileSimulator(assessor=assessor)
    profile = _profile(default_level=LEVEL_CRITICAL)  # profile says CRITICAL...

    result = simulator.simulate(profile, {"scope_id": "scope-1", "tool_name": "lookup", "arguments": {}})
    # ...but the real assessor sees a clean, allowed, unregistered-tool-free call -> LOW
    assert result.risk_factors == {}
    conflict = next(c for c in result.conflicts if c["type"] == "profile_assessment_disagreement")
    assert conflict["profile_level"] == LEVEL_CRITICAL
    assert conflict["assessment_level"] == LEVEL_LOW


# --- invalid profile -------------------------------------------------


def test_invalid_profile_type_raises():
    simulator = LLMAgentRiskProfileSimulator()
    with pytest.raises(InvalidRiskProfileSimulationError):
        simulator.simulate({"not": "a profile"}, {})


def test_structurally_invalid_profile_raises():
    simulator = LLMAgentRiskProfileSimulator()
    profile = _profile(default_level="NOT_A_LEVEL")
    with pytest.raises(InvalidRiskProfileSimulationError):
        simulator.simulate(profile, {"tool_name": "delete_file"})


def test_invalid_action_context_raises():
    from backend.agent_policy_risk_assessment import InvalidActionContextError

    simulator = LLMAgentRiskProfileSimulator()
    profile = _profile()
    with pytest.raises(InvalidActionContextError):
        simulator.simulate(profile, "not-a-dict")


# --- zero side effects --------------------------------------------------


def test_simulate_never_mutates_the_profile_object():
    simulator = LLMAgentRiskProfileSimulator()
    profile = _profile(action_rules=[_rule("r1", LEVEL_HIGH, {"tool_name": "delete_file"})])
    before = LLMAgentRiskProfile(**{**profile.__dict__})

    simulator.simulate(profile, {"tool_name": "delete_file"})

    assert profile == before


def test_simulate_never_persists_the_profile():
    service = LLMAgentRiskProfileService()
    simulator = LLMAgentRiskProfileSimulator()
    profile = _profile(action_rules=[_rule("r1", LEVEL_HIGH, {"tool_name": "delete_file"})])

    simulator.simulate(profile, {"tool_name": "delete_file"})

    assert service.list("scope-1") == []


def test_simulate_is_deterministic():
    simulator = LLMAgentRiskProfileSimulator()
    profile = _profile(action_rules=[_rule("r1", LEVEL_HIGH, {"tool_name": "delete_file"})])

    first = simulator.simulate(profile, {"tool_name": "delete_file"})
    second = simulator.simulate(profile, {"tool_name": "delete_file"})
    assert first.risk_level == second.risk_level
    assert first.action == second.action
    assert first.matched_rules == second.matched_rules


# --- simulation/production parity ---------------------------------------


def test_simulation_parity_with_real_service_resolve():
    service = LLMAgentRiskProfileService()
    created = service.create(
        "scope-1", "p1", action_rules=[_rule("r1", LEVEL_CRITICAL, {"tool_name": "delete_file"})], default_level=LEVEL_LOW
    )
    simulator = LLMAgentRiskProfileSimulator()

    production = service.resolve("scope-1", {"tool_name": "delete_file"})
    simulated = simulator.simulate(created, {"tool_name": "delete_file"})

    assert simulated.risk_level == production.level
    assert simulated.matched_rule_id == production.matched_rule_id


def test_simulation_previews_a_not_yet_activated_profile():
    service = LLMAgentRiskProfileService()
    live = service.create("scope-1", "p1", default_level=LEVEL_LOW)
    draft = _profile(profile_id=live.profile_id, action_rules=[_rule("r1", LEVEL_CRITICAL, {"tool_name": "delete_file"})])
    simulator = LLMAgentRiskProfileSimulator()

    # The live, persisted profile is still unaffected by simulating a draft.
    simulated = simulator.simulate(draft, {"tool_name": "delete_file"})
    production = service.resolve("scope-1", {"tool_name": "delete_file"})

    assert simulated.risk_level == LEVEL_CRITICAL
    assert production.level == LEVEL_LOW


# --- provenance ----------------------------------------------------------


def test_provenance_embeds_profile_and_action_context():
    simulator = LLMAgentRiskProfileSimulator()
    profile = _profile(action_rules=[_rule("r1", LEVEL_HIGH, {"tool_name": "delete_file"})])
    action_context = {"tool_name": "delete_file", "arguments": {"path": "/tmp/x"}}

    result = simulator.simulate(profile, action_context)

    assert result.provenance["profile"].profile_id == profile.profile_id
    assert result.provenance["action_context"] == action_context
    assert result.provenance["action_context"] is not action_context
    assert result.profile_version == profile.version
    assert result.scope_id == profile.scope_id


def test_provenance_embeds_real_assessment_when_configured():
    assessor = _real_assessor()
    simulator = LLMAgentRiskProfileSimulator(assessor=assessor)
    profile = _profile()

    result = simulator.simulate(profile, {"scope_id": "scope-1", "tool_name": "lookup", "arguments": {}})
    assert result.provenance["assessment"] is not None
    assert result.provenance["assessment"].risk_level == LEVEL_LOW


def test_provenance_assessment_is_none_when_no_assessor_configured():
    simulator = LLMAgentRiskProfileSimulator()
    profile = _profile()

    result = simulator.simulate(profile, {"tool_name": "anything"})
    assert result.provenance["assessment"] is None
    assert result.risk_factors == {}
