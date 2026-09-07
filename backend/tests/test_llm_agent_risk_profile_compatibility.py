import pytest

from backend.agent_policy_risk_assessment import LEVEL_CRITICAL, LEVEL_HIGH, LEVEL_LOW
from backend.agent_risk_profile import LLMAgentRiskProfileService, RiskProfileActionRule
from backend.agent_risk_profile_compatibility import CompatibilityResult, LLMAgentRiskProfileCompatibility
from backend.agent_risk_profile_resolution import TIER_EXACT_ACTION, TIER_SCOPE_DEFAULT


def _rule(rule_id, level, match=None):
    return RiskProfileActionRule(rule_id=rule_id, match=match or {}, level=level)


def _services():
    return LLMAgentRiskProfileService(), LLMAgentRiskProfileCompatibility()


def _full_target_context(**overrides):
    context = {
        "risk_profile_schema_version": 1,
        "supported_risk_levels": {LEVEL_LOW, LEVEL_HIGH, LEVEL_CRITICAL},
        "supported_match_fields": {"tool_name"},
        "supported_tiers": {TIER_SCOPE_DEFAULT, TIER_EXACT_ACTION},
        "scope_id": "scope-1",
    }
    context.update(overrides)
    return context


# --- compatible profile --------------------------------------------------


def test_compatible_profile():
    service, compatibility = _services()
    profile = service.create(
        "scope-1", "p1", action_rules=[_rule("r1", LEVEL_HIGH, {"tool_name": "delete_file"})], default_level=LEVEL_LOW
    )

    result = compatibility.check(profile, _full_target_context())

    assert isinstance(result, CompatibilityResult)
    assert result.compatible
    assert result.reasons == []
    assert result.profile_id == profile.profile_id
    assert result.profile_version == profile.version


def test_unspecified_capabilities_impose_no_restriction():
    service, compatibility = _services()
    profile = service.create(
        "scope-1", "p1", action_rules=[_rule("r1", LEVEL_HIGH, {"subject": "prod"})], default_level=LEVEL_CRITICAL
    )

    result = compatibility.check(profile, {"scope_id": "scope-1"})
    assert result.compatible


# --- schema/version mismatch -----------------------------------------------


def test_schema_version_mismatch():
    service, compatibility = _services()
    profile = service.create("scope-1", "p1")

    result = compatibility.check(profile, _full_target_context(risk_profile_schema_version=0))
    assert not result.compatible
    assert any("schema version" in reason for reason in result.reasons)


def test_compatible_schema_version_upgrade():
    service, compatibility = _services()
    profile = service.create("scope-1", "p1")

    result = compatibility.check(profile, _full_target_context(risk_profile_schema_version=5))
    assert result.compatible


def test_invalid_schema_version_type():
    service, compatibility = _services()
    profile = service.create("scope-1", "p1")

    result = compatibility.check(profile, _full_target_context(risk_profile_schema_version="1"))
    assert not result.compatible


# --- unsupported factor (risk level) ---------------------------------------


def test_unsupported_factor_reported():
    service, compatibility = _services()
    profile = service.create(
        "scope-1", "p1", action_rules=[_rule("r1", LEVEL_CRITICAL, {"tool_name": "delete_file"})]
    )

    result = compatibility.check(profile, _full_target_context(supported_risk_levels={LEVEL_LOW}))
    assert not result.compatible
    assert LEVEL_CRITICAL in result.provenance["missing_risk_levels"]
    assert any("risk factor" in reason and "CRITICAL" in reason for reason in result.reasons)


# --- unsupported action ----------------------------------------------------


def test_unsupported_action_field_reported():
    service, compatibility = _services()
    profile = service.create(
        "scope-1", "p1", action_rules=[_rule("r1", LEVEL_HIGH, {"subject": "prod"})]
    )

    result = compatibility.check(profile, _full_target_context(supported_match_fields={"tool_name"}))
    assert not result.compatible
    assert "subject" in result.provenance["unsupported_action_fields"]


def test_unsupported_specificity_tier_reported():
    service, compatibility = _services()
    profile = service.create("scope-1", "p1", action_name="delete_file")

    result = compatibility.check(profile, _full_target_context(supported_tiers={TIER_SCOPE_DEFAULT}))
    assert not result.compatible
    assert result.provenance["missing_tier"] == TIER_EXACT_ACTION


# --- missing capability (target scope configuration) -----------------------


def test_invalid_target_scope_configuration():
    service, compatibility = _services()
    profile = service.create("scope-1", "p1")

    result = compatibility.check(profile, _full_target_context(scope_id=""))
    assert not result.compatible
    assert any("target scope configuration" in reason for reason in result.reasons)


def test_profile_scope_mismatch_with_target_scope_reported():
    service, compatibility = _services()
    profile = service.create("scope-1", "p1")

    result = compatibility.check(profile, _full_target_context(scope_id="scope-2"))
    assert not result.compatible
    assert any("scope-1" in reason and "scope-2" in reason for reason in result.reasons)


def test_invalid_input_types():
    _, compatibility = _services()

    result = compatibility.check("not-a-profile", _full_target_context())
    assert not result.compatible
    assert result.profile_id is None

    service, _ = _services()
    profile = service.create("scope-1", "p1")
    result = compatibility.check(profile, "not-a-dict")
    assert not result.compatible


# --- deterministic result --------------------------------------------------


def test_deterministic_result():
    service, compatibility = _services()
    profile = service.create(
        "scope-1", "p1", action_rules=[_rule("r1", LEVEL_HIGH, {"tool_name": "delete_file"})]
    )

    first = compatibility.check(profile, _full_target_context())
    second = compatibility.check(profile, _full_target_context())
    assert first == second


def test_check_never_mutates_profile():
    service, compatibility = _services()
    profile = service.create("scope-1", "p1")

    compatibility.check(profile, _full_target_context(supported_risk_levels=set()))

    unchanged = service.get(profile.profile_id)
    assert unchanged == profile


# --- reuses existing validation after compatibility succeeds ---------------


def test_reuses_existing_validation_after_compatibility_succeeds():
    from backend.agent_risk_profile import LLMAgentRiskProfile

    # Missing name is invisible to every dedicated compatibility check
    # above (schema/levels/fields/tier/scope all pass) -- only Commit
    # #3's own validator, composed at the end, can catch it.
    corrupted = LLMAgentRiskProfile(scope_id="scope-1", name="", default_level=LEVEL_LOW)
    compatibility = LLMAgentRiskProfileCompatibility()

    result = compatibility.check(corrupted, _full_target_context())
    assert not result.compatible
    assert any(reason.startswith("missing_name") for reason in result.reasons)


def test_validation_skipped_when_a_more_fundamental_incompatibility_exists():
    from backend.agent_risk_profile import LLMAgentRiskProfile

    corrupted = LLMAgentRiskProfile(scope_id="scope-1", name="p1", default_level="NOT_A_LEVEL")
    compatibility = LLMAgentRiskProfileCompatibility()

    result = compatibility.check(corrupted, _full_target_context(risk_profile_schema_version=0))
    assert not result.compatible
    assert "validation_issue_count" not in result.provenance


# --- activation integration -------------------------------------------------


def test_activation_integration():
    from backend.agent_risk_profile_resolution import LLMAgentRiskProfileResolver

    service, compatibility = _services()
    profile = service.create(
        "scope-1", "p1", action_rules=[_rule("r1", LEVEL_CRITICAL, {"tool_name": "delete_file"})]
    )

    compatible_result = compatibility.check(profile, _full_target_context())
    assert compatible_result.compatible

    resolver = LLMAgentRiskProfileResolver(service)
    resolved = resolver.resolve("scope-1", {"tool_name": "delete_file"})
    assert resolved.level == LEVEL_CRITICAL

    # A caller that respects this gate never activates/relies on a profile
    # whose check() reported incompatible -- Commit #1/#2's own
    # create()/resolve() have no notion of "target capabilities" at all
    # and would otherwise proceed regardless, which is exactly why this
    # gate must run first.
    incompatible_result = compatibility.check(profile, _full_target_context(supported_match_fields=set()))
    assert not incompatible_result.compatible
