import pytest

from backend.agent_policy_engine import ALLOW as POLICY_ALLOW
from backend.agent_policy_engine import LLMAgentPolicyRule, LLMAgentPolicyService
from backend.agent_policy_risk_assessment import LEVEL_CRITICAL, LEVEL_HIGH, LEVEL_LOW
from backend.agent_risk_profile import LLMAgentRiskProfileService, RiskProfileActionRule, UnknownRiskProfileError
from backend.agent_risk_profile_activation import RiskProfileScopeMismatchError
from backend.agent_risk_profile_impact_analysis import (
    InvalidRiskProfileImpactAnalysisError,
    LLMAgentRiskProfileImpactAnalyzer,
    RiskProfileImpactResult,
)
from backend.agent_risk_profile_versioning import LLMAgentRiskProfileVersionService, UnknownRiskProfileVersionError
from backend.llm.tools import LLMToolRegistryService

SCHEMA = {"type": "object", "properties": {}, "required": []}


def _rule(rule_id, level, match=None):
    return RiskProfileActionRule(rule_id=rule_id, match=match or {}, level=level)


def _services():
    profile_service = LLMAgentRiskProfileService()
    version_service = LLMAgentRiskProfileVersionService(profile_service)
    analyzer = LLMAgentRiskProfileImpactAnalyzer(profile_service, version_service)
    return profile_service, version_service, analyzer


# --- no dependencies -----------------------------------------------------


def test_profile_with_no_dependencies_produces_an_empty_impact_set():
    profile_service, version_service, analyzer = _services()
    profile = profile_service.create("scope-1", "p1", default_level=LEVEL_LOW)
    version_service.create_version(profile.profile_id)

    result = analyzer.analyze(profile.profile_id, 1, "scope-1")

    assert isinstance(result, RiskProfileImpactResult)
    assert result.affected_actions == []
    assert result.affected_capabilities == []
    assert result.affected_policies == []
    assert result.affected_scopes == ["scope-1"]
    assert result.risk_level_changes == []
    assert result.blocking_conflicts == []
    assert result.warnings == []


# --- rule change detection -------------------------------------------------


def test_rule_change_affecting_an_action_is_detected():
    profile_service, version_service, analyzer = _services()
    profile = profile_service.create("scope-1", "p1", default_level=LEVEL_LOW)
    version_service.create_version(profile.profile_id)  # v1: no rules, LOW default
    version_service.create_version(
        profile.profile_id, action_rules=[_rule("r1", LEVEL_CRITICAL, {"tool_name": "delete_file"})]
    )  # v2: delete_file -> CRITICAL, now live

    # v1 is no longer live (v2 is) -- analyzing it previews what reverting
    # to it would change for the action v2's own rule currently governs.
    result = analyzer.analyze(profile.profile_id, 1, "scope-1")

    assert "delete_file" in result.affected_actions
    change = next(c for c in result.risk_level_changes if c["action"] == "delete_file")
    assert change["before"] == LEVEL_CRITICAL
    assert change["after"] == LEVEL_LOW
    assert f"{len(result.risk_level_changes)} risk level change" in result.impact_summary


def test_unchanged_version_reports_no_risk_level_changes():
    profile_service, version_service, analyzer = _services()
    profile = profile_service.create(
        "scope-1", "p1", action_rules=[_rule("r1", LEVEL_HIGH, {"tool_name": "delete_file"})]
    )
    version_service.create_version(profile.profile_id)

    result = analyzer.analyze(profile.profile_id, 1, "scope-1")
    assert result.risk_level_changes == []
    assert "delete_file" in result.affected_actions


# --- referenced capabilities/policies ---------------------------------


def test_affected_capabilities_reflect_referenced_match_fields():
    profile_service, version_service, analyzer = _services()
    profile = profile_service.create(
        "scope-1", "p1", action_rules=[_rule("r1", LEVEL_HIGH, {"tool_name": "delete_file", "subject": "prod"})]
    )
    version_service.create_version(profile.profile_id)

    result = analyzer.analyze(profile.profile_id, 1, "scope-1")
    assert result.affected_capabilities == sorted({"tool_name", "subject"})


def test_affected_policies_includes_real_active_policies_for_the_scope():
    profile_service = LLMAgentRiskProfileService()
    version_service = LLMAgentRiskProfileVersionService(profile_service)
    policy_service = LLMAgentPolicyService()
    policy = policy_service.create(
        "scope-1", "allow-all", [LLMAgentPolicyRule(rule_id="allow", effect=POLICY_ALLOW, match={})]
    )
    analyzer = LLMAgentRiskProfileImpactAnalyzer(profile_service, version_service, policy_service=policy_service)

    profile = profile_service.create("scope-1", "p1")
    version_service.create_version(profile.profile_id)

    result = analyzer.analyze(profile.profile_id, 1, "scope-1")
    assert result.affected_policies == [policy.policy_id]


def test_no_policy_service_configured_leaves_affected_policies_empty():
    profile_service, version_service, analyzer = _services()
    profile = profile_service.create("scope-1", "p1")
    version_service.create_version(profile.profile_id)

    result = analyzer.analyze(profile.profile_id, 1, "scope-1")
    assert result.affected_policies == []


def test_affected_actions_cross_checked_against_real_tool_registry():
    profile_service = LLMAgentRiskProfileService()
    version_service = LLMAgentRiskProfileVersionService(profile_service)
    tool_registry = LLMToolRegistryService()
    tool_registry.register("delete_file", "deletes a file", SCHEMA)
    analyzer = LLMAgentRiskProfileImpactAnalyzer(profile_service, version_service, tool_registry=tool_registry)

    profile = profile_service.create(
        "scope-1",
        "p1",
        action_rules=[
            _rule("r1", LEVEL_HIGH, {"tool_name": "delete_file"}),
            _rule("r2", LEVEL_HIGH, {"tool_name": "unregistered_tool"}),
        ],
    )
    version_service.create_version(profile.profile_id)

    result = analyzer.analyze(profile.profile_id, 1, "scope-1")
    assert result.affected_actions == ["delete_file"]


# --- scope isolation --------------------------------------------------


def test_scope_mismatch_raises():
    profile_service, version_service, analyzer = _services()
    profile = profile_service.create("scope-1", "p1")
    version_service.create_version(profile.profile_id)

    with pytest.raises(RiskProfileScopeMismatchError):
        analyzer.analyze(profile.profile_id, 1, "scope-2")


def test_affected_policies_never_leak_across_scopes():
    profile_service = LLMAgentRiskProfileService()
    version_service = LLMAgentRiskProfileVersionService(profile_service)
    policy_service = LLMAgentPolicyService()
    policy_service.create("scope-2", "other-scope-policy", [LLMAgentPolicyRule(rule_id="allow", effect=POLICY_ALLOW, match={})])
    analyzer = LLMAgentRiskProfileImpactAnalyzer(profile_service, version_service, policy_service=policy_service)

    profile = profile_service.create("scope-1", "p1")
    version_service.create_version(profile.profile_id)

    result = analyzer.analyze(profile.profile_id, 1, "scope-1")
    assert result.affected_policies == []
    assert result.affected_scopes == ["scope-1"]


def test_invalid_target_scope_raises():
    _, _, analyzer = _services()
    with pytest.raises(InvalidRiskProfileImpactAnalysisError):
        analyzer.analyze("any", 1, "")


# --- incompatible/conflicting dependencies ------------------------------


def test_incompatible_version_reported_as_blocking_conflict():
    profile_service, version_service, analyzer = _services()
    profile = profile_service.create(
        "scope-1", "p1", action_rules=[_rule("r1", LEVEL_HIGH, {"subject": "prod"})]
    )
    version_service.create_version(profile.profile_id)

    result = analyzer.analyze(
        profile.profile_id, 1, "scope-1", target_context={"supported_match_fields": {"tool_name"}}
    )
    assert result.blocking_conflicts != []
    assert any("subject" in reason for reason in result.blocking_conflicts)


def test_compatible_version_reports_no_blocking_conflicts():
    profile_service, version_service, analyzer = _services()
    profile = profile_service.create(
        "scope-1", "p1", action_rules=[_rule("r1", LEVEL_HIGH, {"tool_name": "delete_file"})]
    )
    version_service.create_version(profile.profile_id)

    result = analyzer.analyze(
        profile.profile_id, 1, "scope-1", target_context={"supported_match_fields": {"tool_name"}}
    )
    assert result.blocking_conflicts == []


def test_conflicting_matched_rules_reported_as_warning_not_blocking():
    profile_service, version_service, analyzer = _services()
    profile = profile_service.create(
        "scope-1",
        "p1",
        action_rules=[
            _rule("r1", LEVEL_LOW, {"tool_name": "delete_file"}),
            _rule("r2", LEVEL_CRITICAL, {"tool_name": "delete_file"}),
        ],
    )
    version_service.create_version(profile.profile_id)

    result = analyzer.analyze(profile.profile_id, 1, "scope-1")
    assert result.blocking_conflicts == []
    assert any(w["type"] == "conflicting_action_rules" for w in result.warnings)


# --- existing profile vs historical version -------------------------------


def test_existing_active_profile_and_historical_version_independently_analyzable():
    profile_service, version_service, analyzer = _services()
    profile = profile_service.create("scope-1", "p1", default_level=LEVEL_LOW)
    version_service.create_version(profile.profile_id)  # v1
    version_service.create_version(profile.profile_id, default_level=LEVEL_CRITICAL)  # v2, live

    result_v1 = analyzer.analyze(profile.profile_id, 1, "scope-1")
    result_v2 = analyzer.analyze(profile.profile_id, 2, "scope-1")

    assert result_v1.version == 1
    assert result_v2.version == 2
    # v2 is the profile's current state -- analyzing it changes nothing.
    assert result_v2.risk_level_changes == []
    # v1 would lower the default level back down from the current CRITICAL.
    change = next(c for c in result_v1.risk_level_changes if c["action"] is None)
    assert change["before"] == LEVEL_CRITICAL
    assert change["after"] == LEVEL_LOW


def test_unknown_version_raises():
    profile_service, version_service, analyzer = _services()
    profile = profile_service.create("scope-1", "p1")
    version_service.create_version(profile.profile_id)

    with pytest.raises(UnknownRiskProfileVersionError):
        analyzer.analyze(profile.profile_id, 99, "scope-1")


def test_unknown_profile_raises():
    _, _, analyzer = _services()
    with pytest.raises(UnknownRiskProfileError):
        analyzer.analyze("does-not-exist", 1, "scope-1")


# --- no state mutation -----------------------------------------------------


def test_analysis_performs_no_state_mutation():
    profile_service, version_service, analyzer = _services()
    profile = profile_service.create("scope-1", "p1", default_level=LEVEL_LOW)
    version_service.create_version(profile.profile_id)
    version_service.create_version(profile.profile_id, default_level=LEVEL_CRITICAL)

    before = profile_service.get(profile.profile_id)
    analyzer.analyze(profile.profile_id, 1, "scope-1")
    after = profile_service.get(profile.profile_id)

    assert before == after
    assert len(version_service.list_versions(profile.profile_id)) == 2


# --- deterministic results -------------------------------------------------


def test_results_are_deterministic():
    profile_service, version_service, analyzer = _services()
    profile = profile_service.create(
        "scope-1", "p1", action_rules=[_rule("r1", LEVEL_HIGH, {"tool_name": "delete_file"})]
    )
    version_service.create_version(profile.profile_id)

    first = analyzer.analyze(profile.profile_id, 1, "scope-1")
    second = analyzer.analyze(profile.profile_id, 1, "scope-1")

    assert first.affected_actions == second.affected_actions
    assert first.affected_capabilities == second.affected_capabilities
    assert first.risk_level_changes == second.risk_level_changes
    assert first.blocking_conflicts == second.blocking_conflicts
    assert first.impact_summary == second.impact_summary


# --- provenance ----------------------------------------------------------


def test_provenance_embeds_profile_version_and_compatibility():
    profile_service, version_service, analyzer = _services()
    profile = profile_service.create("scope-1", "p1", default_level=LEVEL_LOW)
    version_service.create_version(profile.profile_id)

    result = analyzer.analyze(profile.profile_id, 1, "scope-1")
    assert result.provenance["profile"].profile_id == profile.profile_id
    assert result.provenance["target_version"]["version"] == 1
    assert result.provenance["compatibility"]["compatible"] is True
