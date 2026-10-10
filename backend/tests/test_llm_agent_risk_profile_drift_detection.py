import pytest

from backend.agent_policy_engine import ALLOW as POLICY_ALLOW
from backend.agent_policy_engine import LLMAgentPolicyRule, LLMAgentPolicyService
from backend.agent_policy_risk_assessment import LEVEL_CRITICAL, LEVEL_HIGH, LEVEL_LOW
from backend.agent_risk_profile import LLMAgentRiskProfileService, RiskProfileActionRule, UnknownRiskProfileError
from backend.agent_risk_profile_activation import RiskProfileScopeMismatchError
from backend.agent_risk_profile_drift_detection import (
    COMPATIBILITY_DRIFT,
    CONFIGURATION_DRIFT,
    NO_DRIFT,
    UNKNOWN,
    LLMAgentRiskProfileDriftDetector,
    RiskProfileDriftResult,
)
from backend.agent_risk_profile_impact_analysis import LLMAgentRiskProfileImpactAnalyzer
from backend.agent_risk_profile_versioning import LLMAgentRiskProfileVersionService, UnknownRiskProfileVersionError
from backend.llm.tools import LLMToolRegistryService

SCHEMA = {"type": "object", "properties": {}, "required": []}


def _rule(rule_id, level, match=None):
    return RiskProfileActionRule(rule_id=rule_id, match=match or {}, level=level)


def _services(**analyzer_kwargs):
    profile_service = LLMAgentRiskProfileService()
    version_service = LLMAgentRiskProfileVersionService(profile_service)
    impact_analyzer = LLMAgentRiskProfileImpactAnalyzer(profile_service, version_service, **analyzer_kwargs)
    detector = LLMAgentRiskProfileDriftDetector(profile_service, version_service, impact_analyzer)
    return profile_service, version_service, detector


# --- matching active and expected versions report no drift ---------------


def test_matching_version_reports_no_drift():
    profile_service, version_service, detector = _services()
    profile = profile_service.create(
        "scope-1", "p1", action_rules=[_rule("r1", LEVEL_HIGH, {"tool_name": "delete_file"})]
    )
    version_service.create_version(profile.profile_id)

    result = detector.detect_version(profile.profile_id, 1, "scope-1")
    assert isinstance(result, RiskProfileDriftResult)
    assert result.drift_detected is False
    assert result.drift_type == NO_DRIFT
    assert result.expected_version == 1
    assert result.actual_version == 1


def test_detect_uses_latest_recorded_version_and_reports_no_drift():
    profile_service, version_service, detector = _services()
    profile = profile_service.create("scope-1", "p1", default_level=LEVEL_LOW)
    version_service.create_version(profile.profile_id)
    version_service.create_version(profile.profile_id, default_level=LEVEL_HIGH)

    result = detector.detect(profile.profile_id, "scope-1")
    assert result.drift_detected is False
    assert result.expected_version == 2
    assert result.actual_version == 2


# --- changed risk rules are detected ---------------------------------------


def test_changed_risk_rules_detected_as_configuration_drift():
    profile_service, version_service, detector = _services()
    profile = profile_service.create(
        "scope-1", "p1", action_rules=[_rule("r1", LEVEL_LOW, {"tool_name": "delete_file"})]
    )
    version_service.create_version(profile.profile_id)  # v1: LOW
    version_service.create_version(
        profile.profile_id, action_rules=[_rule("r1", LEVEL_CRITICAL, {"tool_name": "delete_file"})]
    )  # v2: CRITICAL, live

    result = detector.detect_version(profile.profile_id, 1, "scope-1")
    assert result.drift_detected is True
    assert result.drift_type == CONFIGURATION_DRIFT
    assert "delete_file" in result.affected_actions
    assert any("delete_file" in detail for detail in result.details)


# --- version mismatch is detected ------------------------------------------


def test_version_mismatch_reported_in_result_fields():
    profile_service, version_service, detector = _services()
    profile = profile_service.create("scope-1", "p1", default_level=LEVEL_LOW)
    version_service.create_version(profile.profile_id)
    version_service.create_version(profile.profile_id, default_level=LEVEL_HIGH)

    result = detector.detect_version(profile.profile_id, 1, "scope-1")
    assert result.expected_version == 1
    assert result.actual_version == 2
    assert result.expected_version != result.actual_version
    assert any("does not match" in detail for detail in result.details)


# --- capability/policy relationship changes detected ----------------------


def test_affected_capabilities_reflect_analyzer_output():
    profile_service, version_service, detector = _services()
    profile = profile_service.create(
        "scope-1", "p1", action_rules=[_rule("r1", LEVEL_HIGH, {"tool_name": "delete_file", "subject": "prod"})]
    )
    version_service.create_version(profile.profile_id)

    result = detector.detect_version(profile.profile_id, 1, "scope-1")
    assert result.affected_capabilities == sorted({"tool_name", "subject"})


def test_affected_policies_reflect_real_active_policies_for_scope():
    profile_service = LLMAgentRiskProfileService()
    version_service = LLMAgentRiskProfileVersionService(profile_service)
    policy_service = LLMAgentPolicyService()
    policy = policy_service.create(
        "scope-1", "allow-all", [LLMAgentPolicyRule(rule_id="allow", effect=POLICY_ALLOW, match={})]
    )
    impact_analyzer = LLMAgentRiskProfileImpactAnalyzer(profile_service, version_service, policy_service=policy_service)
    detector = LLMAgentRiskProfileDriftDetector(profile_service, version_service, impact_analyzer)

    profile = profile_service.create("scope-1", "p1")
    version_service.create_version(profile.profile_id)

    result = detector.detect_version(profile.profile_id, 1, "scope-1")
    assert result.affected_policies == [policy.policy_id]


def test_compatibility_drift_reported_when_rules_unchanged_but_incompatible():
    profile_service, version_service, detector = _services()
    profile = profile_service.create(
        "scope-1", "p1", action_rules=[_rule("r1", LEVEL_HIGH, {"subject": "prod"})]
    )
    version_service.create_version(profile.profile_id)

    result = detector.detect_version(
        profile.profile_id, 1, "scope-1", target_context={"supported_match_fields": {"tool_name"}}
    )
    assert result.drift_detected is True
    assert result.drift_type == COMPATIBILITY_DRIFT
    assert result.details != []


# --- scope isolation --------------------------------------------------


def test_scope_mismatch_raises():
    profile_service, version_service, detector = _services()
    profile = profile_service.create("scope-1", "p1")
    version_service.create_version(profile.profile_id)

    with pytest.raises(RiskProfileScopeMismatchError):
        detector.detect_version(profile.profile_id, 1, "scope-2")


def test_affected_policies_never_leak_across_scopes():
    profile_service = LLMAgentRiskProfileService()
    version_service = LLMAgentRiskProfileVersionService(profile_service)
    policy_service = LLMAgentPolicyService()
    policy_service.create("scope-2", "other", [LLMAgentPolicyRule(rule_id="allow", effect=POLICY_ALLOW, match={})])
    impact_analyzer = LLMAgentRiskProfileImpactAnalyzer(profile_service, version_service, policy_service=policy_service)
    detector = LLMAgentRiskProfileDriftDetector(profile_service, version_service, impact_analyzer)

    profile = profile_service.create("scope-1", "p1")
    version_service.create_version(profile.profile_id)

    result = detector.detect_version(profile.profile_id, 1, "scope-1")
    assert result.affected_policies == []


# --- undetectable external state is not fabricated -------------------------


def test_archived_profile_reports_unknown_not_a_guess():
    profile_service, version_service, detector = _services()
    profile = profile_service.create("scope-1", "p1")
    version_service.create_version(profile.profile_id)
    profile_service.archive(profile.profile_id)

    result = detector.detect_version(profile.profile_id, 1, "scope-1")
    assert result.drift_type == UNKNOWN
    assert result.drift_detected is False
    assert result.provenance == {}


def test_never_versioned_profile_reports_unknown_via_detect():
    profile_service, version_service, detector = _services()
    profile = profile_service.create("scope-1", "p1")

    result = detector.detect(profile.profile_id, "scope-1")
    assert result.drift_type == UNKNOWN
    assert result.expected_version is None
    assert result.actual_version == 1


def test_no_tool_registry_configured_never_fabricates_affected_actions():
    profile_service, version_service, detector = _services()  # no tool_registry wired into the analyzer
    profile = profile_service.create(
        "scope-1", "p1", action_rules=[_rule("r1", LEVEL_HIGH, {"tool_name": "delete_file"})]
    )
    version_service.create_version(profile.profile_id)

    result = detector.detect_version(profile.profile_id, 1, "scope-1")
    # Still reported: the profile's own rule genuinely references it,
    # even with no external tool registry to cross-check against.
    assert result.affected_actions == ["delete_file"]


# --- historical versions can be checked explicitly -------------------------


def test_historical_version_checked_explicitly_independent_of_latest():
    profile_service, version_service, detector = _services()
    profile = profile_service.create("scope-1", "p1", default_level=LEVEL_LOW)
    version_service.create_version(profile.profile_id)  # v1
    version_service.create_version(profile.profile_id, default_level=LEVEL_HIGH)  # v2
    version_service.create_version(profile.profile_id, default_level=LEVEL_CRITICAL)  # v3, live

    result_v1 = detector.detect_version(profile.profile_id, 1, "scope-1")
    result_v2 = detector.detect_version(profile.profile_id, 2, "scope-1")
    result_v3 = detector.detect_version(profile.profile_id, 3, "scope-1")

    assert result_v1.drift_detected is True
    assert result_v2.drift_detected is True
    assert result_v3.drift_detected is False


def test_unknown_version_raises():
    profile_service, version_service, detector = _services()
    profile = profile_service.create("scope-1", "p1")
    version_service.create_version(profile.profile_id)

    with pytest.raises(UnknownRiskProfileVersionError):
        detector.detect_version(profile.profile_id, 99, "scope-1")


def test_unknown_profile_raises():
    *_, detector = _services()
    with pytest.raises(UnknownRiskProfileError):
        detector.detect("does-not-exist", "scope-1")


# --- no state mutation -----------------------------------------------------


def test_detection_performs_no_state_mutation():
    profile_service, version_service, detector = _services()
    profile = profile_service.create("scope-1", "p1", default_level=LEVEL_LOW)
    version_service.create_version(profile.profile_id)
    version_service.create_version(profile.profile_id, default_level=LEVEL_HIGH)

    before = profile_service.get(profile.profile_id)
    detector.detect_version(profile.profile_id, 1, "scope-1")
    after = profile_service.get(profile.profile_id)

    assert before == after
    assert len(version_service.list_versions(profile.profile_id)) == 2


# --- deterministic results -------------------------------------------------


def test_repeated_checks_are_deterministic():
    profile_service, version_service, detector = _services()
    profile = profile_service.create(
        "scope-1", "p1", action_rules=[_rule("r1", LEVEL_HIGH, {"tool_name": "delete_file"})]
    )
    version_service.create_version(profile.profile_id)
    version_service.create_version(profile.profile_id, action_rules=[])

    first = detector.detect_version(profile.profile_id, 1, "scope-1")
    second = detector.detect_version(profile.profile_id, 1, "scope-1")

    assert first.drift_detected == second.drift_detected
    assert first.drift_type == second.drift_type
    assert first.affected_actions == second.affected_actions
    assert first.details == second.details
